import os
import json
import logging
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

from .config import DATA_DIR
from .database import db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
DEFAULT_SENDER = os.getenv("RESEND_FROM_EMAIL", "EvoNotes OS <onboarding@resend.dev>")
USER_EMAIL = os.getenv("EXECUTIVE_EMAIL", "felipe@zflowtech.com")
APP_BASE_URL = os.getenv("EVONOTES_PUBLIC_URL", "https://zflow.tech/app")

class ResendNotificationEngine:
    """Dispatches executive transactional emails and daily closing digests via Resend."""

    def __init__(self, api_key: Optional[str] = None, sender: Optional[str] = None):
        self.api_key = api_key or os.getenv("RESEND_API_KEY", "")
        self.sender = sender or DEFAULT_SENDER
        self.base_url = APP_BASE_URL

    def send_email(self, to_email: str, subject: str, html_content: str) -> Dict[str, Any]:
        """Sends an email via Resend API."""
        if not self.api_key:
            logging.warning("RESEND_API_KEY is not set. Simulating email dispatch (preview mode).")
            # Save local preview in cache/dispatches
            preview_dir = DATA_DIR.parent / "cache" / "email_dispatches"
            preview_dir.mkdir(parents=True, exist_ok=True)
            preview_file = preview_dir / f"dispatch_{int(datetime.now().timestamp())}.html"
            with open(preview_file, "w", encoding="utf-8") as f:
                f.write(f"<!-- To: {to_email} | Subject: {subject} -->\n" + html_content)
            
            return {
                "status": "SIMULATED",
                "message": "E-mail gerado com sucesso em modo preview. Configure RESEND_API_KEY para disparo real.",
                "preview_file": str(preview_file)
            }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "from": self.sender,
            "to": [to_email],
            "subject": subject,
            "html": html_content
        }

        try:
            res = requests.post("https://api.resend.com/emails", headers=headers, json=payload, timeout=10)
            if res.status_code in [200, 201]:
                data = res.json()
                logging.info(f"Email sent successfully via Resend: {data.get('id')}")
                return {"status": "SUCCESS", "id": data.get("id")}
            else:
                logging.error(f"Resend API error ({res.status_code}): {res.text}")
                return {"status": "ERROR", "detail": res.text}
        except Exception as e:
            logging.error(f"Exception sending email via Resend: {e}")
            return {"status": "ERROR", "detail": str(e)}

    def dispatch_new_meeting_processed(self, file_id: str, to_email: str = USER_EMAIL) -> Dict[str, Any]:
        """Dispatches instant C-Level executive synthesis when a meeting is transcribed."""
        meeting = db.get_meeting(file_id)
        if not meeting:
            return {"status": "ERROR", "detail": "Meeting not found"}

        title = meeting.get("title", "Reunião Executiva")
        duration = round((meeting.get("duration_seconds", 0) / 60), 1) if meeting.get("duration_seconds") else "25.0"
        category = meeting.get("category", "Comercial")
        intel = meeting.get("intelligence", {})
        summary = intel.get("executive_summary", meeting.get("executive_summary", "Síntese em processamento."))
        commitments = intel.get("commitments_and_promises", [])
        participants = intel.get("participants", [])

        # Build clean tasks HTML
        tasks_html = ""
        if commitments:
            tasks_html = "<div style='margin-top: 20px; padding: 16px; background-color: #f8f9fa; border-radius: 12px;'>"
            tasks_html += "<h4 style='margin: 0 0 10px 0; font-size: 13px; color: #111;'>📋 Compromissos & Prazos Mapeados:</h4>"
            for c in commitments:
                owner = c.get('owner', 'Felipe')
                action = c.get('action', '')
                deadline = c.get('deadline_or_context', 'Hoje')
                tasks_html += f"<div style='margin-bottom: 8px; font-size: 12px; color: #333;'>• <b>{owner}:</b> {action} <span style='background: #e2e8f0; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: bold;'>📅 {deadline}</span></div>"
            tasks_html += "</div>"

        # Direct Deep Link
        meeting_link = f"{self.base_url}?meeting_id={file_id}"

        html = f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="utf-8"></head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f4f5f7; margin: 0; padding: 30px 15px;">
            <div style="max-width: 580px; margin: 0 auto; background: #ffffff; border-radius: 20px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.05); padding: 32px;">
                
                <!-- Header -->
                <div style="display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #f0f0f0; padding-bottom: 16px; margin-bottom: 24px;">
                    <div>
                        <span style="font-size: 11px; font-weight: 800; letter-spacing: 0.05em; color: #059669; text-transform: uppercase; background: #ecfdf5; padding: 4px 8px; border-radius: 6px;">🎙️ EvoNotes OS • Síntese Instantânea</span>
                        <h2 style="font-size: 18px; font-weight: 800; color: #111827; margin: 8px 0 0 0;">{title}</h2>
                    </div>
                </div>

                <!-- Meta Pills -->
                <div style="margin-bottom: 20px; font-size: 12px; color: #6b7280;">
                    ⏱️ <b>Duração:</b> {duration} min &nbsp;|&nbsp; 🏷️ <b>Categoria:</b> {category}
                </div>

                <!-- Executive Summary Box -->
                <div style="background: #ffffff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 20px; margin-bottom: 20px;">
                    <h3 style="margin: 0 0 10px 0; font-size: 13px; font-weight: 700; color: #111827;">💡 Síntese C-Level com Decisões:</h3>
                    <p style="margin: 0; font-size: 13px; line-height: 1.6; color: #374151;">{summary}</p>
                </div>

                {tasks_html}

                <!-- Primary CTA Button -->
                <div style="margin-top: 30px; text-align: center;">
                    <a href="{meeting_link}" style="display: inline-block; background-color: #10b981; color: #000000; font-weight: 700; font-size: 13px; text-decoration: none; padding: 12px 28px; border-radius: 50px; box-shadow: 0 4px 14px rgba(16,185,129,0.3);">
                        Abrir Reunião no EvoNotes ➔
                    </a>
                </div>

                <!-- Footer -->
                <div style="margin-top: 32px; border-top: 1px solid #f0f0f0; padding-top: 16px; text-align: center; font-size: 11px; color: #9ca3af;">
                    EvoNotes OS • Intelligence Hub de Voz para Lideranças<br/>
                    ZFlow Tech Holding • Todos os direitos reservados.
                </div>

            </div>
        </body>
        </html>
        """

        subject = f"🎙️ Síntese Executiva: {title} ({duration} min)"
        return self.send_email(to_email, subject, html)

    def dispatch_daily_closing_digest(self, to_email: str = USER_EMAIL) -> Dict[str, Any]:
        """Dispatches 18:30 Daily Closing Digest with tasks depending specifically on the user."""
        all_tasks = db.get_all_tasks(status="PENDING")
        meetings = db.get_all_meetings()

        # Filter tasks that depend specifically on Felipe
        my_tasks = [t for t in all_tasks if "felipe" in t.get("owner", "").lower() or t.get("owner") == "Felipe Donato"]

        # If no specific felipe tasks, take top pending
        if not my_tasks:
            my_tasks = all_tasks[:5]

        # Calculate metrics
        hours_saved = round((len(meetings) * 45) / 60, 1)

        # Build Pending Tasks HTML with Direct Action Links
        tasks_html = ""
        for t in my_tasks:
            task_id = t.get("id")
            action = t.get("action", "")
            deadline = t.get("deadline_or_context", "Hoje")
            meeting_title = t.get("meeting_title", "Reunião")
            
            # Deep link directly to the task in the tasks central view
            task_deep_link = f"{self.base_url}?view=tasks&task_id={task_id}"

            tasks_html += f"""
            <div style="margin-bottom: 12px; padding: 14px; background: #ffffff; border: 1px solid #e5e7eb; border-radius: 12px; display: flex; align-items: center; justify-content: space-between;">
                <div style="flex: 1; padding-right: 12px;">
                    <div style="font-size: 13px; font-weight: 600; color: #111827; margin-bottom: 4px;">{action}</div>
                    <div style="font-size: 11px; color: #6b7280;">
                        <span style="background: #fef3c7; color: #92400e; padding: 2px 6px; border-radius: 4px; font-weight: bold;">📅 {deadline}</span>
                        &nbsp;• Origem: {meeting_title}
                    </div>
                </div>
                <div>
                    <a href="{task_deep_link}" style="display: inline-block; background: #f3f4f6; color: #111827; text-decoration: none; font-size: 11px; font-weight: bold; padding: 6px 12px; border-radius: 8px; white-space: nowrap;">
                        Executar ➔
                    </a>
                </div>
            </div>
            """

        today_str = datetime.now().strftime("%d/%m/%Y")
        subject = f"📊 Fechamento do Dia: {len(my_tasks)} Tarefas Pendentes • {hours_saved}h Poupadas ({today_str})"

        html = f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="utf-8"></head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f4f5f7; margin: 0; padding: 30px 15px;">
            <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 24px; overflow: hidden; box-shadow: 0 10px 35px rgba(0,0,0,0.06); padding: 32px;">
                
                <!-- Header -->
                <div style="border-bottom: 1px solid #f0f0f0; padding-bottom: 20px; margin-bottom: 24px;">
                    <span style="font-size: 11px; font-weight: 800; color: #2563eb; text-transform: uppercase; background: #eff6ff; padding: 4px 8px; border-radius: 6px;">🌇 Daily Executive Closing • 18h30</span>
                    <h2 style="font-size: 20px; font-weight: 800; color: #111827; margin: 10px 0 4px 0;">Fechamento Executivo do Dia ({today_str})</h2>
                    <p style="font-size: 12px; color: #6b7280; margin: 0;">Visão consolidada de reuniões, produtividade e compromissos abertos.</p>
                </div>

                <!-- KPI Banner -->
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 24px;">
                    <div style="background: #f8fafc; padding: 14px; border-radius: 12px; text-align: center; border: 1px solid #f1f5f9;">
                        <div style="font-size: 22px; font-weight: 800; color: #059669;">{hours_saved}h</div>
                        <div style="font-size: 11px; color: #64748b; font-weight: 500;">Poupadas em Atas & FUPs</div>
                    </div>
                    <div style="background: #f8fafc; padding: 14px; border-radius: 12px; text-align: center; border: 1px solid #f1f5f9;">
                        <div style="font-size: 22px; font-weight: 800; color: #dc2626;">{len(my_tasks)}</div>
                        <div style="font-size: 11px; color: #64748b; font-weight: 500;">Tarefas Dependem de Você</div>
                    </div>
                </div>

                <!-- Pending Tasks Section (The Core Value for the User) -->
                <div style="margin-bottom: 24px;">
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
                        <h3 style="margin: 0; font-size: 14px; font-weight: 700; color: #111827;">⚡ Tarefas que Dependem de Você (Ação Direta):</h3>
                        <a href="{self.base_url}?view=tasks" style="font-size: 11px; color: #2563eb; font-weight: 600; text-decoration: none;">Ver Todas ➔</a>
                    </div>
                    {tasks_html}
                </div>

                <!-- Primary CTA -->
                <div style="text-align: center; margin-top: 28px;">
                    <a href="{self.base_url}?view=tasks" style="display: inline-block; background-color: #0f172a; color: #ffffff; font-weight: 700; font-size: 13px; text-decoration: none; padding: 13px 32px; border-radius: 50px; box-shadow: 0 4px 14px rgba(15,23,42,0.25);">
                        Abrir Central de Tarefas no EvoNotes ➔
                    </a>
                </div>

                <!-- Footer -->
                <div style="margin-top: 32px; border-top: 1px solid #f0f0f0; padding-top: 16px; text-align: center; font-size: 11px; color: #9ca3af;">
                    EvoNotes OS • Régua de Disparos Resend<br/>
                    Você está recebendo este e-mail diário porque é o administrador da organização.
                </div>

            </div>
        </body>
        </html>
        """

        return self.send_email(to_email, subject, html)

resend_engine = ResendNotificationEngine()
