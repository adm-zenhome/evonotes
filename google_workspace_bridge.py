import urllib.parse
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

class GoogleWorkspaceBridge:
    """Bridges EvoNotes OS meetings, follow-ups and tasks with Gmail & Google Calendar."""

    @staticmethod
    def generate_gmail_compose_url(to_email: str, subject: str, body: str) -> str:
        """Generates direct 1-click Gmail Web compose URL with pre-filled fields."""
        params = {
            "view": "cm",
            "fs": "1",
            "to": to_email,
            "su": subject,
            "body": body
        }
        return f"https://mail.google.com/mail/?{urllib.parse.urlencode(params)}"

    @staticmethod
    def generate_calendar_event_url(title: str, deadline_str: str, description: str, attendees: Optional[List[str]] = None) -> str:
        """Generates 1-click Google Calendar Event Template URL from meeting task/follow-up."""
        # Parse or default date
        now = datetime.now()
        start_time = now + timedelta(days=1) # Default tomorrow 10h
        
        lower_deadline = deadline_str.lower()
        if "segunda" in lower_deadline:
            days_ahead = (0 - now.weekday() + 7) % 7
            if days_ahead == 0: days_ahead = 7
            start_time = (now + timedelta(days=days_ahead)).replace(hour=10, minute=0, second=0)
        elif "terça" in lower_deadline or "terca" in lower_deadline:
            days_ahead = (1 - now.weekday() + 7) % 7
            start_time = (now + timedelta(days=days_ahead)).replace(hour=14, minute=0, second=0)
        elif "quarta" in lower_deadline:
            days_ahead = (2 - now.weekday() + 7) % 7
            start_time = (now + timedelta(days=days_ahead)).replace(hour=15, minute=0, second=0)
        elif "hoje" in lower_deadline:
            start_time = now.replace(hour=18, minute=0, second=0)
        elif "amanhã" in lower_deadline or "amanha" in lower_deadline:
            start_time = (now + timedelta(days=1)).replace(hour=10, minute=0, second=0)

        end_time = start_time + timedelta(minutes=45)

        # Format ISO compact for Google Calendar (YYYYMMDDTHHMMSSZ)
        dates_param = f"{start_time.strftime('%Y%m%dT%H%M%S')}/{end_time.strftime('%Y%m%dT%H%M%S')}"

        params = {
            "action": "TEMPLATE",
            "text": f"🎯 EvoNotes: {title}",
            "dates": dates_param,
            "details": description + "\n\n---\n⚡ Agendado automaticamente via EvoNotes OS"
        }

        if attendees:
            params["add"] = ",".join(attendees)

        return f"https://calendar.google.com/calendar/render?{urllib.parse.urlencode(params)}"

google_bridge = GoogleWorkspaceBridge()
