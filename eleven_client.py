#!/usr/bin/env python3
"""
eleven_client.py — Cliente unificado ElevenLabs para o ecossistema Jarvis OS & oquevem.ai
"""

import os
import json
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")
load_dotenv(ROOT_DIR / "oquevemai-engine" / ".env")
load_dotenv()

BASE_URL = "https://api.elevenlabs.io/v1"

DEFAULT_VOICES = {
    "alex": "CwhRBWXzGAHq8TQ4Fs17",        # Roger / Ressonante, Executivo
    "sophia": "Xb7hH8MSUJpSbSDYk0k2",      # Alice / Clara, Inteligente, Engajadora
    "jarvis": "JBFqnCBsd6RMkjVDRZzb",      # George / Cativante, Seguro e Sofisticado
    "ninar": "EXAVITQu4vr4xnSDxMaL",       # Sarah / Doce, Confortante (Histórias JV)
    "storyteller": "JBFqnCBsd6RMkjVDRZzb", # George / Narrador de Aventuras
    "charlie": "IKne3meq5aSn9XLyUdCD"      # Charlie / Dinâmico e Enérgico
}

class ElevenLabsClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY", "").strip().strip('"').strip("'")
        self.headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json"
        }

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.startswith("sk_"))

    def get_user_info(self) -> Dict[str, Any]:
        """Obtém status da conta, saldo de créditos e plano."""
        if not self.is_configured():
            return {"status": "unconfigured", "error": "Chave API sk_... não configurada"}
        
        req = urllib.request.Request(f"{BASE_URL}/user", headers=self.headers)
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            return {"status": "error", "code": e.code, "message": e.read().decode()}

    def get_voices(self) -> List[Dict[str, Any]]:
        """Lista todas as vozes disponíveis na conta."""
        if not self.is_configured():
            return []
        req = urllib.request.Request(f"{BASE_URL}/voices", headers=self.headers)
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode())
                return data.get("voices", [])
        except Exception:
            return []

    def text_to_speech(
        self,
        text: str,
        voice_id: Optional[str] = None,
        voice_alias: str = "jarvis",
        output_file: Optional[Path] = None,
        model_id: str = "eleven_multilingual_v2",
        stability: float = 0.5,
        similarity_boost: float = 0.75
    ) -> Optional[bytes]:
        """
        Gera áudio a partir de texto usando ElevenLabs TTS.
        """
        if not self.is_configured():
            print("⚠️ [ElevenLabs] Chave API não configurada.")
            return None

        selected_voice = voice_id or DEFAULT_VOICES.get(voice_alias, DEFAULT_VOICES["jarvis"])
        url = f"{BASE_URL}/text-to-speech/{selected_voice}"

        payload = {
            "text": text,
            "model_id": model_id,
            "voice_settings": {
                "stability": stability,
                "similarity_boost": similarity_boost
            }
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=self.headers,
            method="POST"
        )

        try:
            with urllib.request.urlopen(req) as resp:
                audio_bytes = resp.read()
                if output_file:
                    output_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(output_file, "wb") as f:
                        f.write(audio_bytes)
                    print(f"✅ Áudio ElevenLabs gerado com sucesso: {output_file}")
                return audio_bytes
        except urllib.error.HTTPError as e:
            print(f"❌ Erro ElevenLabs TTS ({e.code}): {e.read().decode()}")
            return None
        except Exception as e:
            print(f"❌ Erro de conexão ElevenLabs: {e}")
            return None

    def generate_sound_effect(
        self,
        prompt: str,
        output_file: Path,
        duration_seconds: Optional[float] = None
    ) -> Optional[bytes]:
        """
        Gera efeitos sonoros via ElevenLabs Sound Generation API.
        """
        if not self.is_configured():
            print("⚠️ [ElevenLabs] Chave API não configurada.")
            return None

        url = f"{BASE_URL}/sound-generation"
        payload = {"text": prompt}
        if duration_seconds:
            payload["duration_seconds"] = duration_seconds

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=self.headers,
            method="POST"
        )

        try:
            with urllib.request.urlopen(req) as resp:
                audio_bytes = resp.read()
                output_file.parent.mkdir(parents=True, exist_ok=True)
                with open(output_file, "wb") as f:
                    f.write(audio_bytes)
                print(f"✅ Efeito Sonoro gerado: {output_file}")
                return audio_bytes
        except Exception as e:
            print(f"❌ Erro ao gerar efeito sonoro: {e}")
            return None
