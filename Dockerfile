FROM python:3.11-slim

WORKDIR /app

# Install ffmpeg for Whisper audio chunking
RUN apt-get update && apt-get install -y --no-install-recommends     ffmpeg     curl     && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8765
EXPOSE 8765

CMD uvicorn dashboard.app:app --host 0.0.0.0 --port ${PORT:-8765}
