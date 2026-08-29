import os
import sys
from pathlib import Path
import uvicorn

# Ensure root directory is in sys.path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Read PORT from environment (Railway passes PORT dynamically)
PORT = int(os.environ.get("PORT", 8765))
HOST = "0.0.0.0"

if __name__ == "__main__":
    print(f"🚀 [EvoNotes] Launching Executive Voice OS Server on {HOST}:{PORT}...")
    uvicorn.run(
        "dashboard.app:app",
        host=HOST,
        port=PORT,
        log_level="info",
        proxy_headers=True,
        forwarded_allow_ips="*"
    )
