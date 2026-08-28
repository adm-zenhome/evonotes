import os
from pathlib import Path
from dotenv import dotenv_values, load_dotenv

# Load environment variables
ROOT_DIR = Path(__file__).resolve().parent
JARVIS_DIR = ROOT_DIR.parent.parent
env_jarvis = dotenv_values("/Users/felipe/Jarvis/.env")

# Directories
DESKTOP_ZENDESK_DIR = Path.home() / "Desktop" / "Zendesk"
CACHE_DIR = ROOT_DIR / "cache"
DATA_DIR = ROOT_DIR / "data"
DATABASE_FILE = DATA_DIR / "meetings_db.json"
QUEUE_FILE = DESKTOP_ZENDESK_DIR / ".plaud_sync_queue.json"

# API Keys (Jarvis .env takes priority)
OPENAI_API_KEY = env_jarvis.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = env_jarvis.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY", "")
GOOGLE_API_KEY = env_jarvis.get("GOOGLE_API_KEY") or env_jarvis.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")
GEMINI_API_KEY = GOOGLE_API_KEY

# Server Settings
DASHBOARD_HOST = "127.0.0.1"
DASHBOARD_PORT = 8765
POLLING_INTERVAL_SECONDS = 30
CHUNK_DURATION_SECONDS = 600  # 10 minutes per chunk for parallel transcription

# Ensure directories exist
DESKTOP_ZENDESK_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)
