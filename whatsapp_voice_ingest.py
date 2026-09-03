"""
WhatsApp Voice Ingest Engine — Executive Voice OS (EvoNotes)
Receives audio/voice memos forwarded or sent via WhatsApp (Meta Cloud API & Z-API),
transcribes in parallel via Whisper, synthesizes with LLM (IntelligenceEngine),
replies with a 3-bullet executive summary and to-dos in < 5s,
and persists everything into SQLite database and Desktop.
"""

import os
import re
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
    "EAAXwYUV5YAsBSZAbfYYhrF10KpNMCaVLa9hat5WG08xJEdAe51yTZATXaNO5TAQSUDNZAU7wVaPWScx1ZBJyKe0Fbhd83qLw5AmjRjNsKxkGn01HlEJonQRMq2coiWZAjUobsbMDS1NxLONI5LOjMMiqZAGktZCDkI9mzio7m710xqKEDLvI47tneyNBnpTbRDjFAZDZD"
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

# Global state for interactive action contexts
_PENDING_ACTION_CONTEXTS = {}

def normalize_whatsapp_phone(raw_phone: str) -> str:
    import re
    digits = re.sub(r'\D', '', str(raw_phone))
    if digits.startswith('0') and len(digits) in [11, 12]:
        digits = digits[1:]
    if len(digits) in [10, 11]:
        digits = '55' + digits
    return digits

def get_brazilian_phone_variations(clean_phone: str) -> list:
    variations = [clean_phone]
    if clean_phone.startswith("55"):
        # If 13 digits (55XX9XXXXXXX)
        if len(clean_phone) == 13 and clean_phone[4] == '9':
            alt = clean_phone[:4] + clean_phone[5:]
            if alt not in variations:
                variations.append(alt)
        # If 12 digits (55XXXXXXXXXX)
        elif len(clean_phone) == 12:
            alt = clean_phone[:4] + '9' + clean_phone[4:]
            if alt not in variations:
                variations.append(alt)
    return variations

class WhatsAppVoiceIngest:
    def __init__(self):
        self.audio_pipeline = AudioPipeline()
        self.intelligence_engine = IntelligenceEngine()

    def send_whatsapp_auth_template(self, phone: str, otp_code: str) -> bool:
        clean_phone = normalize_whatsapp_phone(phone)
        targets = get_brazilian_phone_variations(clean_phone)
        any_success = False

        for target in targets:
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
                        "to": target,
                        "type": "template",
                        "template": {
                            "name": "evonotes_auth_code",
                            "language": {"code": "pt_BR"},
                            "components": [
                                {
                                    "type": "body",
                                    "parameters": [{"type": "text", "text": str(otp_code)}]
                                },
                                {
                                    "type": "button",
                                    "sub_type": "url",
                                    "index": "0",
                                    "parameters": [{"type": "text", "text": str(otp_code)}]
                                }
                            ]
                        }
                    }
                    r = httpx.post(url, json=payload, headers=headers, timeout=15)
                    if r.status_code in [200, 201]:
                        logger.info(f"Official Meta 2FA template sent successfully to {target}")
                        any_success = True
                    else:
                        logger.warning(f"Meta template to {target} returned {r.status_code}: {r.text}")
                except Exception as e:
                    logger.warning(f"Meta template send error to {target}: {e}")

            if not any_success:
                fallback_msg = (
                    f"🔐 *Código de Acesso EvoNotes OS*\n\n"
                    f"Seu código de acesso é: *{otp_code}*\n\n"
                    f"Digite este código no painel para entrar no seu Segundo Cérebro de Voz.\n"
                    f"⏳ Válido por 5 minutos."
                )
                if self.send_whatsapp_text(target, fallback_msg):
                    any_success = True

        return any_success

    def send_whatsapp_text(self, phone: str, text: str) -> bool:
        clean_phone = normalize_whatsapp_phone(phone)
        
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

    def send_whatsapp_buttons(self, phone: str, text: str, buttons: list, header_text: str = None) -> bool:
        """
        Envia Botões Interativos Nativos da Meta WhatsApp Cloud API (até 3 botões rápidos de 1 toque).
        """
        clean_phone = normalize_whatsapp_phone(phone)
        if META_WA_TOKEN and META_WA_PHONE_NUMBER_ID:
            try:
                url = f"{META_WA_BASE_URL}/messages"
                headers = {"Authorization": f"Bearer {META_WA_TOKEN}", "Content-Type": "application/json"}
                
                button_items = []
                for b in buttons[:3]:
                    button_items.append({
                        "type": "reply",
                        "reply": {
                            "id": b["id"],
                            "title": b["title"][:20]  # Limite rígido da Meta: 20 caracteres
                        }
                    })
                
                interactive_payload = {
                    "type": "button",
                    "body": {"text": text[:1024]},
                    "action": {"buttons": button_items}
                }
                if header_text:
                    interactive_payload["header"] = {"type": "text", "text": header_text[:60]}
                
                payload = {
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": clean_phone,
                    "type": "interactive",
                    "interactive": interactive_payload
                }
                r = httpx.post(url, json=payload, headers=headers, timeout=15)
                if r.status_code in [200, 201]:
                    logger.info(f"Meta interactive buttons sent successfully to {clean_phone}")
                    return True
                else:
                    logger.warning(f"Meta buttons returned {r.status_code}: {r.text}, falling back to text...")
            except Exception as e:
                logger.warning(f"Error sending Meta interactive buttons: {e}")
        
        # Fallback formatado com números caso a Meta falhe
        lines = [text, "", "━━━━━━━━━━━━━━━━━━━━"]
        for idx, b in enumerate(buttons[:3], 1):
            lines.append(f"{idx}️⃣ *[{idx}]* {b['title']}")
        lines.append("\n_(Responda com o número correspondente)_")
        return self.send_whatsapp_text(clean_phone, "\n".join(lines))

    def send_whatsapp_reaction(self, phone: str, message_id: str, emoji: str = "⚡") -> bool:
        """
        Envia uma reação de emoji oficial (ex: 👍, ⚡, 🎯, ✅) na mensagem do usuário.
        """
        clean_phone = normalize_whatsapp_phone(phone)
        if META_WA_TOKEN and META_WA_PHONE_NUMBER_ID and message_id:
            try:
                url = f"{META_WA_BASE_URL}/messages"
                headers = {"Authorization": f"Bearer {META_WA_TOKEN}", "Content-Type": "application/json"}
                payload = {
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": clean_phone,
                    "type": "reaction",
                    "reaction": {
                        "message_id": message_id,
                        "emoji": emoji
                    }
                }
                r = httpx.post(url, json=payload, headers=headers, timeout=10)
                return r.status_code in [200, 201]
            except Exception as e:
                logger.warning(f"Reaction send failed: {e}")
        return False

    def mark_whatsapp_read(self, message_id: str) -> bool:
        """
        Marca a mensagem como lida (ticks azuis) na Meta Cloud API.
        """
        if META_WA_TOKEN and META_WA_PHONE_NUMBER_ID and message_id:
            try:
                url = f"{META_WA_BASE_URL}/messages"
                headers = {"Authorization": f"Bearer {META_WA_TOKEN}", "Content-Type": "application/json"}
                payload = {
                    "messaging_product": "whatsapp",
                    "status": "read",
                    "message_id": message_id
                }
                r = httpx.post(url, json=payload, headers=headers, timeout=10)
                return r.status_code in [200, 201]
            except Exception as e:
                logger.warning(f"Mark read failed: {e}")
        return False

    def send_whatsapp_action_menu(self, phone: str, summary_text: str, context_payload: dict = None) -> bool:
        clean_phone = normalize_whatsapp_phone(phone)
        if context_payload:
            _PENDING_ACTION_CONTEXTS[clean_phone] = {
                **context_payload,
                "timestamp": time.time()
            }
        
        # Meta Cloud API Interactive List / Buttons
        if META_WA_TOKEN and META_WA_PHONE_NUMBER_ID:
            try:
                url = f"{META_WA_BASE_URL}/messages"
                headers = {"Authorization": f"Bearer {META_WA_TOKEN}", "Content-Type": "application/json"}
                
                # Interactive List with 4 Small Action Buttons
                payload = {
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": clean_phone,
                    "type": "interactive",
                    "interactive": {
                        "type": "list",
                        "body": {
                            "text": (summary_text[:900] + "\n\n⚡ *O que deseja fazer com este conteúdo?*")
                        },
                        "action": {
                            "button": "⚡ Escolher Ação",
                            "sections": [
                                {
                                    "title": "Ações Rápidas",
                                    "rows": [
                                        {"id": "action_save_note", "title": "📝 Salvar como Nota", "description": "Gera briefing e salva no painel"},
                                        {"id": "action_create_tasks", "title": "✅ Criar Tarefas", "description": "Cadastra pendências com prazos"},
                                        {"id": "action_email_followup", "title": "📧 Follow-up E-mail", "description": "Gera rascunho de e-mail"},
                                        {"id": "action_dismiss", "title": "💬 Apenas Conversa", "description": "Mantém no chat sem salvar"}
                                    ]
                                }
                            ]
                        }
                    }
                }
                r = httpx.post(url, json=payload, headers=headers, timeout=15)
                if r.status_code in [200, 201]:
                    logger.info(f"Interactive 4-action list sent successfully to {clean_phone}")
                    return True
                else:
                    logger.warning(f"Meta interactive list returned {r.status_code}: {r.text}, falling back to text...")
            except Exception as e:
                logger.warning(f"Error sending Meta interactive list: {e}")

        # Fallback text with clear 4 choices
        menu_text = (
            f"{summary_text}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ *O que deseja fazer com este conteúdo?*\n\n"
            f"1️⃣ *[1]* 📝 Salvar como Nota Oficial no Painel\n"
            f"2️⃣ *[2]* ✅ Criar Tarefas na Central de Tarefas\n"
            f"3️⃣ *[3]* 📧 Gerar Rascunho de Follow-up (E-mail)\n"
            f"4️⃣ *[4]* 💬 Apenas Conversa (Não salvar)\n\n"
            f"_(Responda apenas com o número **1**, **2**, **3** ou **4**)_"
        )
        return self.send_whatsapp_text(clean_phone, menu_text)

    def _execute_action_choice(self, action_key: str, phone: str, user_id: str) -> Optional[str]:
        clean_phone = normalize_whatsapp_phone(phone)
        ctx = _PENDING_ACTION_CONTEXTS.get(clean_phone)
        if not ctx:
            return None

        action_key = str(action_key).strip().lower()

        if action_key in ["1", "action_save_note", "salvar", "salvar nota", "nota", "salvar como nota"]:
            intel = ctx.get("intel", {})
            msg_id = ctx.get("msg_id", f"wa_{int(time.time())}")
            raw_text = ctx.get("raw_text", "")
            target_audio = ctx.get("target_audio", "")
            transcript_data = ctx.get("transcript_data", {})
            
            self._persist_meeting_and_tasks(msg_id, clean_phone, intel, raw_text, target_audio, transcript_data)
            _PENDING_ACTION_CONTEXTS.pop(clean_phone, None)
            return "📝 **Nota Oficial Salva com Sucesso!**\n\nO briefing completo, transcrição e áudio já estão disponíveis no seu Dashboard."

        elif action_key in ["2", "action_create_tasks", "tarefa", "tarefas", "criar tarefas", "criar tarefa"]:
            intel = ctx.get("intel", {})
            msg_id = ctx.get("msg_id", f"wa_{int(time.time())}")
            tasks = intel.get("commitments_and_promises", [])
            if not tasks:
                tasks = [{"action": "Revisar pontos da mensagem", "owner": "Você", "deadline": "Hoje"}]
                
            for t in tasks:
                action = t.get("action") or t.get("description", "")
                if action:
                    db.create_task(
                        meeting_id=msg_id,
                        action=action,
                        owner=t.get("owner", "Você"),
                        deadline=t.get("deadline_or_context") or t.get("deadline", "Hoje")
                    )
            _PENDING_ACTION_CONTEXTS.pop(clean_phone, None)
            return f"✅ **{len(tasks)} Tarefa(s) Cadastrada(s)!**\n\nOs itens de ação com donos e prazos foram adicionados à sua Central de Tarefas."

        elif action_key in ["3", "action_email_followup", "followup", "email", "follow-up", "e-mail"]:
            intel = ctx.get("intel", {})
            emails = intel.get("follow_up_emails", [])
            if emails:
                e = emails[0]
                to_p = e.get("to", "Participantes")
                subj = e.get("subject", "Follow-up de Alinhamento")
                body = e.get("body", "Obrigado pela reunião. Seguem os combinados...")
            else:
                to_p = "Equipe / Cliente"
                subj = f"Follow-up: {intel.get('meeting_title', 'Alinhamento')}"
                body = f"Olá,\n\nSeguem os principais tópicos alinhados:\n\n{intel.get('executive_summary', '')}\n\nFico à disposição."

            reply = (
                f"📧 *RASCUNHO DE FOLLOW-UP DE E-MAIL:*\n\n"
                f"📌 *Para:* {to_p}\n"
                f"📝 *Assunto:* {subj}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"{body}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"_(Basta copiar o texto acima e enviar)_"
            )
            _PENDING_ACTION_CONTEXTS.pop(clean_phone, None)
            return reply

        elif action_key in ["4", "action_dismiss", "descartar", "cancelar", "apenas conversa", "conversa"]:
            _PENDING_ACTION_CONTEXTS.pop(clean_phone, None)
            return "👍 **Entendido!** Mensagem mantida apenas como conversa rápida, sem registrar nada no painel."

        return None

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

            # Check for interactive button/list reply
            if msg_type == "interactive":
                inter = msg.get("interactive", {})
                action_id = inter.get("list_reply", {}).get("id") or inter.get("button_reply", {}).get("id", "")
                reply_txt = self._execute_action_choice(action_id, sender_phone, user_id)
                if reply_txt:
                    self.send_whatsapp_text(sender_phone, reply_txt)
                    return {"status": "SUCCESS", "mode": "INTERACTIVE_ACTION_EXECUTED", "action": action_id}

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

                # Se for Comando de Voz ou Pergunta Curta (< 15s)
                if not is_memo and duration <= 15 and intent in ["LIST_TASKS", "LIST_NOTES", "COMMAND_TASK", "QUESTION", "STATUS"]:
                    reply_msg = intent_data.get("reply_msg", "Comando de voz executado com sucesso.")
                    tasks = intent_data.get("tasks_to_create", [])
                    for t in tasks:
                        action = t.get("action")
                        if action:
                            db.create_task(
                                meeting_id=msg_id,
                                action=action,
                                owner=t.get("owner", "Você"),
                                deadline=t.get("deadline", "Hoje")
                            )
                    if sender_phone:
                        self.send_whatsapp_text(sender_phone, reply_msg)
                    return {"status": "SUCCESS", "mode": "VOICE_COMMAND", "reply": reply_msg, "processing_time": duration_s}

                # Se for Áudio de Conteúdo/Reunião: Gera Síntese e Pergunta com os 4 Botões de Ação
                meta = {
                    "file_id": msg_id,
                    "name": f"Áudio WhatsApp — {datetime.now().strftime('%d/%m %H:%M')}",
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "duration": duration,
                    "sender_phone": sender_phone,
                    "source_type": "WHATSAPP_CLOUD_API"
                }
                intel = self.intelligence_engine.analyze(raw_text, metadata=meta, user_id=user_id)
                summary_reply = self._build_whatsapp_reply(intel, raw_text, duration_s)
                
                # Envia Resumo + Menu Interativo de 4 Ações (NÃO salva automaticamente)
                if sender_phone:
                    context_payload = {
                        "msg_id": msg_id,
                        "raw_text": raw_text,
                        "intel": intel,
                        "meta": meta,
                        "target_audio": str(target_audio),
                        "transcript_data": transcript_data
                    }
                    self.send_whatsapp_action_menu(sender_phone, summary_reply, context_payload)

                return {"status": "SUCCESS", "mode": "ACTION_MENU_PRESENTED", "file_id": msg_id, "processing_time": duration_s}

            elif msg_type == "text":
                text_body = msg.get("text", {}).get("body", "")
                if text_body:
                    return self._process_text_memo(text_body, sender_phone, user_id, start_time)
                return {"status": "SKIPPED", "reason": "EMPTY_TEXT"}

            return {"status": "SKIPPED", "reason": f"UNSUPPORTED_TYPE_{msg_type}"}

        except Exception as e:
            logger.error(f"Error in Meta webhook: {e}", exc_info=True)
            return {"status": "ERROR", "error": str(e)}
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
        
        # 0. Check for interactive action choices (1, 2, 3, 4)
        action_reply = self._execute_action_choice(text, phone, user_id)
        if action_reply:
            if phone:
                self.send_whatsapp_text(phone, action_reply)
            return {"status": "SUCCESS", "mode": "ACTION_EXECUTED", "reply": action_reply}

        # 0.1 Intercept Instant Handshake Login / Auth Code
        code_match = re.search(r'(?:EVO-[\w\d]+|AUTH-[\w\d]+|\b\d{6}\b)', text, re.IGNORECASE)
        candidate_code = code_match.group(0) if code_match else text.strip()
        auth_result = db.authorize_auth_session_by_code(candidate_code, sender_phone=phone)
        
        if not auth_result and any(w in text.upper() for w in ["ATIVAR", "ENTRAR", "LOGIN", "QUERO ENTRAR", "OI"]):
            with db.get_connection() as conn:
                cursor = conn.cursor()
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("SELECT session_id, auth_code FROM auth_sessions WHERE is_authorized = 0 AND expires_at > ? ORDER BY created_at DESC LIMIT 1", (now_str,))
                row = cursor.fetchone()
                if row:
                    auth_result = db.authorize_auth_session_by_code(row["auth_code"], sender_phone=phone)

        if auth_result:
            welcome_name = "Felipe Donato" if auth_result["user_id"] == "felipe_donato" else f"Membro {auth_result['phone'][-4:]}"
            reply = (
                f"🎉 *Acesso Autorizado!*\n\n"
                f"Olá, {welcome_name}! Sua sessão foi autenticada com sucesso no navegador.\n\n"
                f"Você já pode voltar para a tela do computador ou celular — seu Dashboard foi aberto na hora!\n"
                f"Todos os áudios e comandos de voz enviados por aqui serão processados pelo seu Segundo Cérebro de Voz em tempo real."
            )
            if phone:
                self.send_whatsapp_text(phone, reply)
            return {"status": "SUCCESS", "mode": "AUTH_HANDSHAKE_COMPLETED", "session_id": auth_result["session_id"], "user_id": auth_result["user_id"]}

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

        if is_memo or len(text) > 200:
            # Rota: MEMO / CONTEXTO LONGO: Gera Síntese e Menu de 4 Ações (NÃO salva direto)
            intel = self.intelligence_engine.analyze(text, metadata=meta, user_id=user_id)
            duration_s = round(time.time() - start_time, 1)
            summary_reply = self._build_whatsapp_reply(intel, text, duration_s)

            if phone:
                context_payload = {
                    "msg_id": msg_id,
                    "raw_text": text,
                    "intel": intel,
                    "meta": meta,
                    "target_audio": "",
                    "transcript_data": {"text": text, "duration": 10}
                }
                self.send_whatsapp_action_menu(phone, summary_reply, context_payload)

            return {"status": "SUCCESS", "mode": "ACTION_MENU_PRESENTED", "file_id": msg_id, "processing_time": duration_s}

        # Rota: PERGUNTA / COMANDO / CONVERSA RÁPIDA
        duration_s = round(time.time() - start_time, 1)
        
        # Criação de Tarefa Rápida se comando explícito
        tasks = intent_data.get("tasks_to_create", [])
        for t in tasks:
            action = t.get("action")
            if action:
                db.create_task(
                    meeting_id=msg_id,
                    action=action,
                    owner=t.get("owner", "Você"),
                    deadline=t.get("deadline", "Hoje")
                )

        if phone:
            self.send_whatsapp_text(phone, reply_msg)

        return {"status": "SUCCESS", "mode": "CONVERSATION_REPLY", "reply": reply_msg, "processing_time": duration_s}

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
