import os
import sys
import threading
from pathlib import Path
import uvicorn

# Ensure root directory is in sys.path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

def start_server(port_num):
    print(f"🚀 [EvoNotes] Starting FastAPI listener on 0.0.0.0:{port_num}...")
    try:
        uvicorn.run(
            "dashboard.app:app",
            host="0.0.0.0",
            port=port_num,
            log_level="info",
            proxy_headers=True,
            forwarded_allow_ips="*"
        )
    except Exception as e:
        print(f"⚠️ Listener on port {port_num} stopped: {e}")

if __name__ == "__main__":
    env_port = int(os.environ.get("PORT", 8080))
    target_ports = list(dict.fromkeys([env_port, 8765, 8080]))
    print(f"🌟 [EvoNotes] Launching universal dual-port listeners on: {target_ports}")
    
    # Launch secondary ports in background threads
    for p in target_ports[1:]:
        t = threading.Thread(target=start_server, args=(p,), daemon=True)
        t.start()
    
    # Run primary port in main thread
    start_server(target_ports[0])
