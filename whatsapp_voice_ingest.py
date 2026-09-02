"""
WhatsApp Voice Ingest Engine — Executive Voice OS (EvoNotes)
Receives audio/voice memos forwarded or sent via WhatsApp (Meta Cloud API & Z-API),
transcribes in parallel via Whisper, synthesizes with LLM (IntelligenceEngine),
replies with a 3-bullet executive summary and to-dos in < 5s,
and persists everything into SQLite database and Desktop.
"""

import os
import time
import logging
import httpx
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

from config import CACHE_DIR, DESKTOP_ZENDESK_DIR
from database import db
from audio_pipeline import AudioPipeline
from intelligence_engine import IntelligenceEngine

logger = logging.getLogger("WhatsAppVoiceIngest")

# Meta WhatsApp Cloud API Credentials
META_WA_TOKEN = os.environ.get(
    "META_WA_TOKEN", 
    "EAAXwYUV5YAsBSRirZCm5lKg1qMhgczjmb1n99sC8ENezAuoPxwkuViGvmEzQXlJEfy1lb8jP5XxhS0YlLNFpahpHvZBDLOS1ZBZCbM5WjmSOVMnuAbKO1PLNLJI5ZCnBLtZAzK34HytsGZCqfUZAa5uNZBpZCGNkrOOCD0hcq7nciPASPajzGdMP63WhUHCC1MOOIKZAAZDZD"
)
META_WA_PHONE_NUMBER_ID = os.environ.get("META_WA_PHONE_NUMBER_ID", "1288311671030624")
META_WA_WABA_ID = os.environ.get("META_WA_WABA_ID", "1615247683296412")
META_WA_VERIFY_TOKEN = os.environ.get("META_WA_VERIFY_TOKEN", "evonotes_webhook_token_2026")
META_WA_BASE_URL = f"https://graph.facebook.com/v22.0/{META_WA_PHONE_NUMBER_ID}"

# Z-API Credentials (Fallback)
INSTANCE_ID = os.environ.get("ZAPI_INSTANCE_ID", "3F07699C1A6F71D36752A6B015A329C7")
TOKEN = os.environ.get("ZAPI_TOKEN", "FB677694F01990951F2DE560")
CLIENT_TOKEN = os.environ.get("ZAPI_CLIENT_TOKEN", "Fe3901d4f2b4e4862bfb1ab045b769b88S")
ZAPI_BASE_URL = f"https://api.z-api.io/instances/{INSTANCE_ID}/token/{TOKEN}"
ZAPI_HEADERS = {"Client-Token": CLIENT_TOKEN, "Content-Type": "application/json"}


class WhatsAppVoiceIngest:
    def __init__(self):
        self.audio_pipeline = AudioPipeline()
        self.intelligence_engine = IntelligenceEngine()

    def send_whatsapp_text(self, phone: str, text: str) -> bool:
        clean_phone = phone.replace("+", "").replace("-", "").replace(" ", "").replace("@c.us", "").replace("@g.us", "")
        
        if META_WA_TOKEN and META_WA_PHONE_NUMBER_ID:
            try:
                url = f"{META_WA_BASE_URL}/messages"
                headers = {
                    "Authorization": f"Bearer {META_WA_TOKEN}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": clean_phone,
                    "type": "text",
                    "text": {"preview_url": False, "body": text}
                }
                r = httpx.post(url, json=payload, headers=headers, timeout=15)
                if r.status_code in [200, 201]:
                    logger.info(f"Meta WhatsApp Cloud API reply sent successfully to {clean_phone}")
                    return True
                else:
                    logger.warning(f"Meta Cloud API returned {r.status_code}: {r.text}, trying Z-API fallback...")
            except Exception as e:
                logger.warning(f"Meta Cloud API send error: {e}, trying Z-API fallback...")

        try:
            url = f"{ZAPI_BASE_URL}/send-text"
            payload = {"phone": clean_phone, "message": text}
            r = httpx.post(url, json=payload, headers=ZAPI_HEADERS, timeout=15)
            if r.status_code in [200, 201]:
                logger.info(f"WhatsApp reply sent successfully to {clean_phone} via Z-API")
                return True
            else:
                logger.error(f"Z-API error {r.status_code}: {r.text}")
                return False
        except Exception as e:
            logger.error(f"Failed to send WhatsApp message: {e}")
            return False

    async def fetch_and_process_latest_audio(self, phone: str, user_id: str = "felipe_donato") -> Dict[str, Any]:
        clean_phone = phone.replace("+", "").replace("-", "").replace(" ", "").replace("@c.us", "").replace("@g.us", "")
        url = f"{ZAPI_BASE_URL}/chat-messages/{clean_phone}"
        
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.get(url, headers=ZAPI_HEADERS)
                if r.status_code == 200:
                    messages = r.json()
                    if isinstance(messages, list):
                        for msg in messages:
                            m_type = str(msg.get("type", "")).lower()
                            audio_url = ""
                            if "audio" in msg and isinstance(msg["audio"], dict):
                                audio_url = msg["audio"].get("audioUrl") or msg["audio"].get("url", "")
                            elif "audioUrl" in msg:
                                audio_url = msg.get("audioUrl")
                            elif "url" in msg and ("audio" in m_type or "voice" in m_type or "ptt" in m_type):
                                audio_url = msg.get("url")

                            if audio_url:
                                return await self.process_webhook({
                                    "id": msg.get("id") or f"wa_pull_{int(time.time())}",
                                    "phone": clean_phone,
                                    "type": "audio",
                                    "audioUrl": audio_url,
                                    "fromMe": msg.get("fromMe", False)
                                }, user_id=user_id)
        except Exception as e:
            logger.warning(f"Could not pull WhatsApp chat: {e}")

        return {"status": "SUCCESS", "phone": clean_phone, "mode": "LISTENER_ACTIVATED"}

    async def process_webhook(self, payload: Dict[str, Any], user_id: str = "felipe_donato") -> Dict[str, Any]:
        start_time = time.time()
        logger.info(f"Received WhatsApp webhook payload: keys={list(payload.keys())}")

        if payload.get("object") == "whatsapp_business_account" or "entry" in payload:
            return await self._process_meta_cloud_webhook(payload, user_id, start_time)

        return await self._process_zapi_webhook(payload, user_id, start_time)

    async def _process_meta_cloud_webhook(self, payload: Dict[str, Any], user_id: str, start_time: float) -> Dict[str, Any]:
        try:
            entry = payload.get("entry", [{}])[0]
            changes = entry.get("changes", [{}])[0]
            val = changes.get("value", {})
            messages = val.get("messages", [])

            if not messages:
                return {"status": "SKIPPED", "reason": "STATUS_UPDATE"}

            msg = messages[0]
            sender_phone = msg.get("from", "")
            msg_id = msg.get("id", f"wa_meta_{int(time.time())}")
            msg_type = msg.get("type", "")

            if msg_type in ["audio", "voice"]:
                media_info = msg.get("audio") or msg.get("voice", {})
                media_id = media_info.get("id")
                if not media_id:
                    return {"status": "SKIPPED", "reason": "NO_MEDIA_ID"}

                target_audio = CACHE_DIR / f"{msg_id}.ogg"
                async with httpx.AsyncClient(timeout=30) as client:
                    meta_url = f"https://graph.facebook.com/v22.0/{media_id}"
                    headers = {"Authorization": f"Bearer {META_WA_TOKEN}"}
                    r_info = await client.get(meta_url, headers=headers)
                    if r_info.status_code != 200:
                        return {"status": "ERROR", "error": "MEDIA_URL_FAILED"}
                    
                    media_download_url = r_info.json().get("url")
                    if not media_download_url:
                        return {"status": "ERROR", "error": "NO_DOWNLOAD_URL"}

                    r_file = await client.get(media_download_url, headers=headers)
                    with open(target_audio, "wb") as f:
                        f.write(r_file.content)

                transcript_data = self.audio_pipeline.process(
                    target_audio,
                    msg_id,
                    prompt="WhatsApp Voice memo, Zendesk, ZCC, clientes, propostas, pipeline, decisões, follow-up, reuniões"
                )
                raw_text = transcript_data.get("text", "") or "(Áudio sem fala detectada)"

                duration = transcript_data.get("duration", 0)
                duration_s = round(time.time() - start_time, 1)

                # 1. Roteamento Inteligente de Intenção do Áudio
                intent_data = self.intelligence_engine.route_and_process_text(raw_text, user_id=user_id)
                intent = intent_data.get("intent", "QUESTION")
                is_memo = intent_data.get("is_memo", False)

                # Se for Comando de Voz ou Pergunta Curta (< 20s e não for memo narrativo longo)
                if not is_memo and duration <= 20 and intent in ["LIST_TASKS", "LIST_NOTES", "COMMAND_TASK", "QUESTION", "STATUS"]:
                    reply_msg = intent_data.get("reply_msg", "Comando de voz executado com sucesso.")
                    tasks = intent_data.get("tasks_to_create", [])
                    for t in tasks:
                        action = t.get("action")
                        if action:
                            db.create_task(
                                meeting_id=msg_id,
                                action=action,
                                owner=t.get("owner", "Felipe Donato"),
                                deadline=t.get("deadline", "Hoje")
                            )
                    if sender_phone:
                        self.send_whatsapp_text(sender_phone, reply_msg)
                    return {"status": "SUCCESS", "mode": "VOICE_COMMAND", "reply": reply_msg, "processing_time": duration_s}

                # Se for Reunião Real ou Nota de Áudio Longa (> 20s ou memo explícito)
                meta = {
                    "file_id": msg_id,
                    "name": f"WhatsApp Voice — {datetime.now().strftime('%d/%m %H:%M')}",
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "duration": duration,
                    "sender_phone": sender_phone,
                    "source_type": "WHATSAPP_CLOUD_API"
                }
                intel = self.intelligence_engine.analyze(raw_text, metadata=meta, user_id=user_id)
                reply_msg = self._build_whatsapp_reply(intel, raw_text, duration_s)
                if sender_phone:
                    self.send_whatsapp_text(sender_phone, reply_msg)

                self._persist_meeting_and_tasks(msg_id, sender_phone, intel, raw_text, target_audio, transcript_data)
                return {"status": "SUCCESS", "file_id": msg_id, "title": intel.get("meeting_title"), "processing_time": duration_s}

            elif msg_type == "text":
                text_body = msg.get("text", {}).get("body", "")
                if text_body:
                    return self._process_text_memo(text_body, sender_phone, user_id, start_time)
                return {"status": "SKIPPED", "reason": "EMPTY_TEXT"}

            return {"status": "SKIPPED", "reason": f"UNSUPPORTED_TYPE_{msg_type}"}

        except Exception as e:
            logger.error(f"Error in Meta webhook: {e}", exc_info=True)
            return {"status": "ERROR", "error": str(e)}

    async def _process_zapi_webhook(self, payload: Dict[str, Any], user_id: str, start_time: float) -> Dict[str, Any]:
        if payload.get("fromMe", False):
            return {"status": "SKIPPED", "reason": "FROM_ME"}

        phone = payload.get("phone", "") or payload.get("senderPhone", "")
        msg_type = str(payload.get("type", "")).lower()

        audio_url = ""
        if "audio" in payload and isinstance(payload["audio"], dict):
            audio_url = payload["audio"].get("audioUrl") or payload["audio"].get("url", "")
        elif "audioUrl" in payload:
            audio_url = payload.get("audioUrl")
        elif "url" in payload and ("audio" in msg_type or "voice" in msg_type or "ptt" in msg_type):
            audio_url = payload.get("url")

        if not audio_url and msg_type in ["text", "chat", "conversation"]:
            text_body = payload.get("text", {}).get("message") or payload.get("message", "")
            if text_body:
                return self._process_text_memo(text_body, phone, user_id, start_time)
            return {"status": "SKIPPED", "reason": "NO_CONTENT"}

        if not audio_url:
            return {"status": "SKIPPED", "reason": f"UNSUPPORTED_TYPE_{msg_type}"}

        msg_id = payload.get("messageId") or payload.get("id") or f"wa_{int(time.time())}"
        target_audio = CACHE_DIR / f"{msg_id}.ogg"
        
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(audio_url)
            resp.raise_for_status()
            with open(target_audio, "wb") as f:
                f.write(resp.content)

        transcript_data = self.audio_pipeline.process(
            target_audio, 
            msg_id, 
            prompt="WhatsApp Voice memo, Zendesk, ZCC, clientes, propostas, pipeline, decisões, follow-up, reuniões"
        )
        raw_text = transcript_data.get("text", "") or "(Áudio sem fala detectada)"

        # 1. Roteamento Inteligente de Intenção do Áudio
        intent_data = self.intelligence_engine.route_and_process_text(raw_text, user_id=user_id)
        intent = intent_data.get("intent", "QUESTION")
        is_memo = intent_data.get("is_memo", False)
        duration_s = round(time.time() - start_time, 1)

        # Se for Comando de Voz ou Pergunta Curta
        duration = transcript_data.get("duration", 0)
        if not is_memo and duration <= 20 and intent in ["LIST_TASKS", "LIST_NOTES", "COMMAND_TASK", "QUESTION", "STATUS"]:
            reply_msg = intent_data.get("reply_msg", "Comando de voz executado com sucesso.")
            tasks = intent_data.get("tasks_to_create", [])
            for t in tasks:
                action = t.get("action")
                if action:
                    db.create_task(
                        meeting_id=msg_id,
                        action=action,
                        owner=t.get("owner", "Felipe Donato"),
                        deadline=t.get("deadline", "Hoje")
                    )
            if phone:
                self.send_whatsapp_text(phone, reply_msg)
            return {"status": "SUCCESS", "mode": "VOICE_COMMAND", "reply": reply_msg, "processing_time": duration_s}

        meta = {
            "file_id": msg_id,
            "name": f"WhatsApp Voice — {datetime.now().strftime('%d/%m %H:%M')}",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "duration": transcript_data.get("duration", 0),
            "sender_phone": phone,
            "source_type": "WHATSAPP_ZAPI"
        }
        intel = self.intelligence_engine.analyze(raw_text, metadata=meta, user_id=user_id)

        reply_msg = self._build_whatsapp_reply(intel, raw_text, duration_s)
        if phone:
            self.send_whatsapp_text(phone, reply_msg)

        self._persist_meeting_and_tasks(msg_id, phone, intel, raw_text, target_audio, transcript_data)
        return {"status": "SUCCESS", "file_id": msg_id, "title": intel.get("meeting_title"), "processing_time": duration_s}

    def _persist_meeting_and_tasks(self, msg_id: str, phone: str, intel: Dict[str, Any], raw_text: str, target_audio: Path, transcript_data: Dict[str, Any]):
        title_slug = intel.get("meeting_title", "WhatsApp_Voice").replace("/", "-").replace(" ", "_")
        doc_path = DESKTOP_ZENDESK_DIR / f"WHATSAPP_{datetime.now().strftime('%Y-%m-%d')}_📱_{title_slug}.md"
        
        try:
            with open(doc_path, "w", encoding="utf-8") as f:
                lines = [
                    "---",
                    "tipo: whatsapp-voice-memo",
                    f'id_mensagem: "{msg_id}"',
                    f'remetente: "{phone}"',
                    f'data: "{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}"',
                    f'categoria: "{intel.get("category", "Pessoal")}"',
                    "status: processado",
                    "---",
                    "",
                    f"# 📱 {intel.get('meeting_title', 'WhatsApp Voice Memo')}",
                    "",
                    "## 🎯 Síntese Executiva:",
                    intel.get("executive_summary", ""),
                    "",
                    "## 📋 Compromissos & To-Dos:"
                ]
                for c in intel.get("commitments_and_promises", []):
                    lines.append(f"- **[{c.get('owner', 'Ação')}]:** {c.get('action', '')}")
                lines.extend([
                    "",
                    "## 📝 Transcrição Original:",
                    "<details>",
                    "<summary>Clique para ver o texto completo</summary>",
                    "",
                    raw_text,
                    "",
                    "</details>",
                    ""
                ])
                f.write("\n".join(lines))
        except Exception as e:
            logger.warning(f"Could not write desktop markdown: {e}")

        db.save_meeting({
            "file_id": msg_id,
            "title": f"📱 {intel.get('meeting_title', 'WhatsApp Voice Memo')}",
            "duration": int(transcript_data.get("duration", 0)),
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "audio_path": str(target_audio),
            "audio_url": f"/api/audio/{msg_id}",
            "doc_path": str(doc_path),
            "executive_summary": intel.get("executive_summary", ""),
            "intelligence": intel,
            "transcript_full": raw_text,
            "custom_notes": f"Ingerido via WhatsApp ({phone})"
        })

        todos = intel.get("commitments_and_promises", [])
        for todo in todos:
            action = todo.get("action")
            if action:
                try:
                    db.create_task(
                        meeting_id=msg_id,
                        action=action,
                        owner=todo.get("owner", "Felipe Donato"),
                        deadline=todo.get("deadline_or_context", "Hoje")
                    )
                except Exception as e:
                    logger.warning(f"Could not insert task into DB: {e}")

    def _build_whatsapp_reply(self, intel: Dict[str, Any], raw_text: str, duration_s: float) -> str:
        summary = intel.get("executive_summary", "").strip()
        todos = intel.get("commitments_and_promises", [])
        accounts = intel.get("accounts_discussed", [])

        msg_lines = [
            f"🎯 *SÍNTESE EXECUTIVA ({intel.get('meeting_title', 'Áudio')}):*",
            summary,
            ""
        ]

        if todos:
            msg_lines.append("📋 *COMPROMISSOS & TO-DOS:*")
            for t in todos[:4]:
                owner = t.get("owner", "Você")
                action = t.get("action", "")
                deadline = t.get("deadline_or_context")
                deadline_str = f" _(Prazo: {deadline})_" if deadline and deadline != "N/A" else ""
                msg_lines.append(f"• *[{owner}]* {action}{deadline_str}")
            msg_lines.append("")

        if accounts:
            msg_lines.append("🏢 *DEALS & CONTAS:*")
            for acc in accounts[:3]:
                msg_lines.append(f"• *{acc.get('account_name')}*: {acc.get('opportunity_or_risk', '')}")
            msg_lines.append("")

        msg_lines.append(f"⚡ _Processado pelo EvoNotes OS em {duration_s}s_")
        return "\n".join(msg_lines)

    def _process_text_memo(self, text: str, phone: str, user_id: str, start_time: float) -> Dict[str, Any]:
        msg_id = f"wa_txt_{int(time.time())}"
        meta = {
            "file_id": msg_id,
            "name": f"Nota WhatsApp — {datetime.now().strftime('%d/%m %H:%M')}",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "sender_phone": phone,
            "source_type": "WHATSAPP_TEXT"
        }

        # 1. Roteamento Inteligente de Intenção (Intent Router)
        intent_data = self.intelligence_engine.route_and_process_text(text, user_id=user_id)
        intent = intent_data.get("intent", "QUESTION")
        reply_msg = intent_data.get("reply_msg", "Comando processado.")
        is_memo = intent_data.get("is_memo", False)

        if is_memo or len(text) > 300:
            # Rota: ÁUDIO / MEMO LONGO (Textos longos)
            intel = self.intelligence_engine.analyze(text, metadata=meta, user_id=user_id)
            duration_s = round(time.time() - start_time, 1)
            reply_msg = self._build_whatsapp_reply(intel, text, duration_s)

            if phone:
                self.send_whatsapp_text(phone, reply_msg)

            db.save_meeting({
                "file_id": msg_id,
                "title": f"💬 {intel.get('meeting_title', 'Mensagem WhatsApp')}",
                "duration": 10,
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "audio_path": "",
                "audio_url": "",
                "doc_path": "",
                "executive_summary": intel.get("executive_summary", ""),
                "intelligence": intel,
                "transcript_full": text,
                "custom_notes": f"Ingerido via WhatsApp Texto ({phone})"
            })
            return {"status": "SUCCESS", "file_id": msg_id, "processing_time": duration_s}

        # Rota: PERGUNTA / COMANDO / CONVERSA / KNOWLEDGE_SEARCH
        duration_s = round(time.time() - start_time, 1)
        
        # Criação de Tarefa Rápida no SQLite
        tasks = intent_data.get("tasks_to_create", [])
        for t in tasks:
            action = t.get("action")
            if action:
                db.create_task(
                    meeting_id=msg_id,
                    action=action,
                    owner=t.get("owner", "Felipe Donato"),
                    deadline=t.get("deadline", "Hoje")
                )

        if phone:
            self.send_whatsapp_text(phone, reply_msg)

        # Retorna resposta sem poluir a lista de reuniões com mensagens efêmeras de chat
        return {"status": "SUCCESS", "reply": reply_msg, "processing_time": duration_s}


def check_zapi_status() -> Dict[str, Any]:
    if META_WA_TOKEN and META_WA_PHONE_NUMBER_ID:
        try:
            url = f"https://graph.facebook.com/v22.0/{META_WA_PHONE_NUMBER_ID}"
            headers = {"Authorization": f"Bearer {META_WA_TOKEN}"}
            with httpx.Client(timeout=5) as client:
                r = client.get(url, headers=headers)
                if r.status_code == 200:
                    data = r.json()
                    return {
                        "is_connected": True,
                        "phone": data.get("display_phone_number", "+55 11 96000-4895"),
                        "status": "CONNECTED",
                        "provider": "META_CLOUD_API",
                        "verified_name": data.get("verified_name", "EvoNotes AI Agent")
                    }
        except Exception as e:
            logger.warning(f"Meta Cloud API check warning: {e}")

    try:
        url = f"{ZAPI_BASE_URL}/status"
        with httpx.Client(timeout=5) as client:
            r = client.get(url, headers=ZAPI_HEADERS)
            if r.status_code == 200:
                data = r.json()
                return {
                    "is_connected": bool(data.get("connected", False)),
                    "phone": data.get("phone", ""),
                    "status": "CONNECTED" if data.get("connected") else "DISCONNECTED",
                    "provider": "ZAPI"
                }
    except Exception as e:
        logger.warning(f"Error querying Z-API status: {e}")

    return {
        "is_connected": False,
        "phone": "",
        "status": "DISCONNECTED",
        "message": "Nenhum canal de WhatsApp ativo no momento"
    }
