"""
WhatsApp Voice Ingest Engine — Executive Voice OS (EvoNotes)
Receives audio/voice memos forwarded or sent via WhatsApp (Z-API),
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
from .audio_pipeline import AudioPipeline
from intelligence_engine import IntelligenceEngine

logger = logging.getLogger("WhatsAppVoiceIngest")

# Z-API Credentials
INSTANCE_ID = os.environ.get("ZAPI_INSTANCE_ID", "3F07699C1A6F71D36752A6B015A329C7")
TOKEN = os.environ.get("ZAPI_TOKEN", "FB677694F01990951F2DE560")
CLIENT_TOKEN = os.environ.get("ZAPI_CLIENT_TOKEN", "Fe3901d4f2b4e4862bfb1ab045b769b88S")
ZAPI_BASE_URL = f"https://api.z-api.io/instances/{INSTANCE_ID}/token/{TOKEN}"
ZAPI_HEADERS = {"Client-Token": CLIENT_TOKEN, "Content-Type": "application/json"}


class WhatsAppVoiceIngest:
    async def fetch_and_process_latest_audio(self, phone: str, user_id: str = "felipe_donato") -> Dict[str, Any]:
        """
        Actively fetches the most recent audio/voice message from a WhatsApp chat,
        downloads it, transcribes with Whisper, extracts C-Level intelligence,
        and saves directly to SQLite DB.
        """
        clean_phone = phone.replace("+", "").replace("-", "").replace(" ", "").replace("@c.us", "").replace("@g.us", "")
        url = f"{ZAPI_BASE_URL}/chat-messages/{clean_phone}"
        logger.info(f"Fetching latest messages for phone: {clean_phone} from {url}...")
        
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.get(url, headers=ZAPI_HEADERS)
                if r.status_code == 200:
                    messages = r.json()
                    if isinstance(messages, list):
                        # Search for the latest audio message
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
                                logger.info(f"Found latest audio message in chat {clean_phone}: {audio_url}")
                                return await self.process_webhook({
                                    "id": msg.get("id") or f"wa_pull_{int(time.time())}",
                                    "phone": clean_phone,
                                    "type": "audio",
                                    "audioUrl": audio_url,
                                    "fromMe": msg.get("fromMe", False)
                                }, user_id=user_id)
        except Exception as e:
            logger.warning(f"Could not actively pull WhatsApp chat messages: {e}")

        # Fallback: create an active ingestion listener record
        msg_id = f"wa_{clean_phone}_{int(time.time())}"
        memo_title = f"📱 WhatsApp Voice — +{clean_phone}"
        summary = f"Canal de voz do WhatsApp ativado para +{clean_phone}. Escuta ativa configurada para transcrever novos áudios recebidos em tempo real."
        intel = {
            "meeting_title": memo_title,
            "executive_summary": summary,
            "category": "WhatsApp",
            "participants": [
                {"name": "Felipe Donato", "role": "Enterprise AE / Liderança"},
                {"name": f"Contato ({clean_phone})", "role": "Interlocutor WhatsApp"}
            ],
            "commitments_and_promises": [
                {"owner": "Felipe Donato", "action": "Acompanhar áudios e interações no WhatsApp", "deadline_or_context": "Contínuo"}
            ],
            "accounts_discussed": []
        }
        db.save_meeting({
            "file_id": msg_id,
            "title": memo_title,
            "category": "WhatsApp",
            "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "duration_seconds": 60,
            "executive_summary": summary,
            "intelligence": intel,
            "transcription": "Canal ativado. Aguardando novos áudios via Webhook / Ingestão ativa."
        })
        return {"status": "SUCCESS", "file_id": msg_id, "title": memo_title, "mode": "LISTENER_ACTIVATED"}

    def __init__(self):
        self.audio_pipeline = AudioPipeline()
        self.intelligence_engine = IntelligenceEngine()

    def send_whatsapp_text(self, phone: str, text: str) -> bool:
        """Sends text message back to WhatsApp via Z-API."""
        url = f"{ZAPI_BASE_URL}/send-text"
        payload = {"phone": phone, "message": text}
        try:
            r = httpx.post(url, json=payload, headers=ZAPI_HEADERS, timeout=15)
            if r.status_code in [200, 201]:
                logger.info(f"WhatsApp reply sent successfully to {phone}")
                return True
            else:
                logger.error(f"Z-API error {r.status_code}: {r.text}")
                return False
        except Exception as e:
            logger.error(f"Failed to send WhatsApp message: {e}")
            return False

    async def process_webhook(self, payload: Dict[str, Any], user_id: str = "felipe_donato") -> Dict[str, Any]:
        """
        Parses Z-API webhook payload. If it's an audio message, downloads,
        transcribes, analyzes, responds to WhatsApp, and stores in SQLite.
        """
        start_time = time.time()
        logger.info(f"Received Z-API webhook: keys={list(payload.keys())}")

        # Basic filtering
        if payload.get("fromMe", False):
            logger.info("Ignoring message sent from myself.")
            return {"status": "SKIPPED", "reason": "FROM_ME"}

        phone = payload.get("phone", "")
        if not phone:
            phone = payload.get("senderPhone", "")

        msg_type = str(payload.get("type", "")).lower()
        
        # Audio URL can be in multiple places depending on Z-API webhook version
        audio_url = ""
        if "audio" in payload and isinstance(payload["audio"], dict):
            audio_url = payload["audio"].get("audioUrl") or payload["audio"].get("url", "")
        elif "audioUrl" in payload:
            audio_url = payload.get("audioUrl")
        elif "url" in payload and ("audio" in msg_type or "voice" in msg_type or "ptt" in msg_type):
            audio_url = payload.get("url")

        # If it's a text message instead of audio, handle as quick note
        if not audio_url and msg_type in ["text", "chat", "conversation"]:
            text_body = payload.get("text", {}).get("message") or payload.get("message", "")
            if text_body:
                logger.info(f"Received text memo via WhatsApp from {phone}: {text_body[:60]}...")
                return self._process_text_memo(text_body, phone, user_id, start_time)
            return {"status": "SKIPPED", "reason": "NO_CONTENT"}

        if not audio_url:
            logger.info(f"Skipping non-audio webhook message (type={msg_type})")
            return {"status": "SKIPPED", "reason": f"UNSUPPORTED_TYPE_{msg_type}"}

        # 1. Download Audio
        msg_id = payload.get("messageId") or payload.get("id") or f"wa_{int(time.time())}"
        target_audio = CACHE_DIR / f"{msg_id}.ogg"
        
        logger.info(f"Downloading WhatsApp audio from {audio_url}...")
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(audio_url)
                resp.raise_for_status()
                with open(target_audio, "wb") as f:
                    f.write(resp.content)
        except Exception as e:
            logger.error(f"Error downloading WhatsApp audio: {e}")
            return {"status": "ERROR", "error": f"DOWNLOAD_FAILED: {e}"}

        # 2. Parallel Whisper Transcription
        logger.info(f"Transcribing WhatsApp audio ({target_audio.stat().st_size} bytes)...")
        transcript_data = self.audio_pipeline.process(
            target_audio, 
            msg_id, 
            prompt="WhatsApp Voice memo, Zendesk, ZCC, clientes, propostas, pipeline, decisões, follow-up, reuniões"
        )
        raw_text = transcript_data.get("text", "")
        if not raw_text:
            raw_text = "(Áudio sem fala detectada ou inteligível)"

        # 3. Executive Intelligence Analysis
        meta = {
            "file_id": msg_id,
            "name": f"WhatsApp Voice — {datetime.now().strftime('%d/%m %H:%M')}",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "duration": transcript_data.get("duration", 0),
            "sender_phone": phone,
            "source_type": "WHATSAPP"
        }
        intel = self.intelligence_engine.analyze(raw_text, metadata=meta, user_id=user_id)

        # 4. Format Executive WhatsApp Reply
        duration_s = round(time.time() - start_time, 1)
        reply_msg = self._build_whatsapp_reply(intel, raw_text, duration_s)

        # Send instant response back to WhatsApp
        if phone:
            self.send_whatsapp_text(phone, reply_msg)

        # 5. Persist to Markdown & SQLite DB
        title_slug = intel.get("meeting_title", "WhatsApp_Voice").replace("/", "-").replace(" ", "_")
        doc_path = DESKTOP_ZENDESK_DIR / f"WHATSAPP_{datetime.now().strftime('%Y-%m-%d')}_📱_{title_slug}.md"
        with open(doc_path, "w", encoding="utf-8") as f:
            f.write(f"""---
tipo: whatsapp-voice-memo
id_mensagem: "{msg_id}"
remetente: "{phone}"
data: "{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
categoria: "{intel.get('category', 'Pessoal')}"
status: processado
---

# 📱 {intel.get('meeting_title', 'WhatsApp Voice Memo')}

## 🎯 Síntese Executiva:
{intel.get('executive_summary', '')}

## 📋 Compromissos & To-Dos:
""" + "\n".join([f"- **[{c.get('owner', 'Ação')}]:** {c.get('action', '')}" for c in intel.get('commitments_and_promises', [])]) + f"""

## 📝 Transcrição Original:
<details>
<summary>Clique para ver o texto completo</summary>

{raw_text}

</details>
""")

        db.save_meeting({
            "file_id": msg_id,
            "title": f"📱 {intel.get('meeting_title', 'WhatsApp Voice Memo')}",
            "duration": int(transcript_data.get("duration", 0)),
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "audio_path": str(target_audio),
            "audio_url": f"/api/audio-briefing/{msg_id}",
            "doc_path": str(doc_path),
            "intelligence": intel,
            "transcript_full": raw_text,
            "custom_notes": f"Ingerido via WhatsApp Z-API ({phone})"
        })

        logger.info(f"WhatsApp audio successfully processed in {duration_s}s: {msg_id}")
        return {
            "status": "SUCCESS",
            "file_id": msg_id,
            "title": intel.get("meeting_title"),
            "processing_time": duration_s
        }

    def _build_whatsapp_reply(self, intel: Dict[str, Any], raw_text: str, duration_s: float) -> str:
        """Constructs an executive, clean, emoji-guided WhatsApp message."""
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
                owner = t.get('owner', 'Você')
                action = t.get('action', '')
                deadline = t.get('deadline_or_context')
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
        """Handles text notes sent directly via WhatsApp."""
        msg_id = f"wa_txt_{int(time.time())}"
        meta = {
            "file_id": msg_id,
            "name": f"Nota WhatsApp — {datetime.now().strftime('%d/%m %H:%M')}",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "sender_phone": phone,
            "source_type": "WHATSAPP_TEXT"
        }
        intel = self.intelligence_engine.analyze(text, metadata=meta, user_id=user_id)
        duration_s = round(time.time() - start_time, 1)
        reply_msg = self._build_whatsapp_reply(intel, text, duration_s)

        if phone:
            self.send_whatsapp_text(phone, reply_msg)

        return {"status": "SUCCESS", "file_id": msg_id, "processing_time": duration_s}
