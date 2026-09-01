#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

# Source virtualenv if available
if [ -f "/Users/felipe/Jarvis/.venv/bin/activate" ]; then
    source "/Users/felipe/Jarvis/.venv/bin/activate"
fi

export PYTHONPATH="$DIR:$DIR/dashboard"
echo "🚀 Iniciando EvoNotes Sandbox na porta 8766..."
python3 -m uvicorn dashboard.app:app --host 127.0.0.1 --port 8766 --reload
