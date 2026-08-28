# 🎙️ EvoNotes OS — Executive Second Brain & Voice Intelligence

O primeiro Sistema Operacional de Inteligência por Voz para Lideranças & C-Level.

## 🚀 Deploy 100% Apartado na Nuvem (Railway / Render / Fly.io / AWS)

### 1. Variáveis de Ambiente Necessárias (.env):
```bash
OPENAI_API_KEY="sk-proj-..."
ELEVENLABS_API_KEY="sk_..."
PLAUD_USER_EMAIL="felipe@zflowtech.com"
```

### 2. Deploy com Docker:
```bash
docker build -t evonotes-os .
docker run -p 8765:8765 -e OPENAI_API_KEY="your_key" evonotes-os
```

### 3. Deploy com Railway / Render:
Basta conectar este repositório (`https://github.com/adm-zenhome/evonotes`). O `Dockerfile` e `Procfile` já estão prontos para deploy automático 24/7.
