#!/bin/bash
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="/Users/felipe/Jarvis:$PYTHONPATH"

echo "🚀 Iniciando Executive Voice OS (Dashboard + Daemon)..."
exec /Users/felipe/.local/bin/uv run --with fastapi --with uvicorn --with jinja2 --with openai uvicorn modules.executive_voice_os.dashboard.app:app --host 127.0.0.1 --port 8765
