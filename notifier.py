import os
import json
import subprocess
import urllib.request
import urllib.parse
import logging
from typing import Dict, Any, Optional
from .config import DASHBOARD_HOST, DASHBOARD_PORT

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "7734494805:AAEybSrLc5O3z0sJCgNYaggcc7EdUIAf1-Q")

class InductionNotifier:
    """Proactive notification and habit-induction system for Executive Voice OS."""

    def __init__(self, bot_token: str = TELEGRAM_BOT_TOKEN):
        self.bot_token = bot_token
        self.dashboard_url = f"http://{DASHBOARD_HOST}:{DASHBOARD_PORT}"

    def send_macos_notification(self, title: str, subtitle: str, message: str):
        """Sends native macOS desktop banner notification with sound."""
        try:
            # Escape double quotes
            safe_title = title.replace('"', '\\"')
            safe_sub = subtitle.replace('"', '\\"')
            safe_msg = message.replace('"', '\\"')
            
            script = f'display notification "{safe_msg}" with title "{safe_title}" subtitle "{safe_sub}" sound name "Glass"'
            subprocess.run(["osascript", "-e", script], check=True)
            logging.info("macOS banner notification sent.")
        except Exception as e:
            logging.error(f"Error sending macOS notification: {e}")

    def get_telegram_chat_id(self) -> Optional[int]:
        """Auto-detects recent Telegram chat ID."""
        url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                results = data.get("result", [])
                if results:
                    last = results[-1]
                    msg = last.get("message") or last.get("channel_post") or last.get("callback_query", {}).get("message")
                    if msg and "chat" in msg:
                        return msg["chat"]["id"]
        except Exception as e:
            logging.error(f"Error getting Telegram chat ID: {e}")
        return None

    def send_telegram_alert(self, intel: Dict[str, Any], doc_path: str):
        """Sends structured Telegram alert with key points and dashboard link."""
        chat_id = self.get_telegram_chat_id()
        if not chat_id:
            logging.warning("No Telegram chat ID found. Skipping Telegram alert.")
            return

        title = intel.get("meeting_title", "Nova Reunião Gravada")
        commitments = intel.get("commitments_and_promises", [])
        
        todos_text = "\n".join([f"• <b>[{c.get('owner', 'Ação')}]</b>: {c.get('action')}" for c in commitments[:3]]) or "• Nenhum to-do crítico."

        message_text = f"""🎙️ <b>Executive Voice OS — Reunião Processada!</b>

<b>{title}</b>
<i>{intel.get('teaser', 'Resumo executivo gerado com sucesso.')}</i>

📋 <b>Principais Compromissos:</b>
{todos_text}

✨ <b>Ações Disponíveis:</b>
👉 <a href="{self.dashboard_url}">Abrir Dashboard Executivo</a>
📂 Arquivo salvo no seu Desktop: <code>{os.path.basename(doc_path)}</code>
"""
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message_text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                logging.info("Telegram alert sent successfully.")
        except Exception as e:
            logging.error(f"Error sending Telegram alert: {e}")

    def trigger_post_meeting_induction(self, intel: Dict[str, Any], doc_path: str):
        """Triggers all notification channels to induce executive habit loop."""
        title = intel.get("meeting_title", "Reunião Processada")
        teaser = intel.get("teaser", "Resumo e Follow-up prontos.")
        commitments_count = len(intel.get("commitments_and_promises", []))
        
        # 1. Desktop Notification
        self.send_macos_notification(
            title="🎙️ Executive Voice OS",
            subtitle=f"{title}",
            message=f"{commitments_count} compromisso(s) mapeado(s). Clique para ver follow-up."
        )
        
        # 2. Telegram Alert
        self.send_telegram_alert(intel, doc_path)

if __name__ == "__main__":
    notifier = InductionNotifier()
    notifier.send_macos_notification("🎙️ Executive Voice OS", "Teste de Indução", "O sistema está 100% ativo e pronto no seu Mac.")
    print("InductionNotifier ready.")
