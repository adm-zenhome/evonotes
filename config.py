import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent

DATA_DIR = ROOT_DIR / "data"
CACHE_DIR = ROOT_DIR / "cache"
DESKTOP_ZENDESK_DIR = ROOT_DIR / "export"

DATA_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DESKTOP_ZENDESK_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_FILE = DATA_DIR / "meetings_db.json"
QUEUE_FILE = DATA_DIR / ".plaud_sync_queue.json"

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY", "")
GEMINI_API_KEY = GOOGLE_API_KEY
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")

DASHBOARD_HOST = "0.0.0.0"
DASHBOARD_PORT = int(os.environ.get("PORT", 8765))
POLLING_INTERVAL_SECONDS = 30
CHUNK_DURATION_SECONDS = 600
