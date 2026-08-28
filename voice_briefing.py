import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from openai import OpenAI

from .config import OPENAI_API_KEY, CACHE_DIR
from ..eleven_client import ElevenLabsClient, DEFAULT_VOICES

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

AUDIO_BRIEFING_DIR = CACHE_DIR / "audio_briefings"
AUDIO_BRIEFING_DIR.mkdir(parents=True, exist_ok=True)

class VoiceBriefingEngine:
    """Generates 60-90s executive audio podcast briefings via ElevenLabs."""

    def __init__(self, eleven_key: Optional[str] = None, openai_key: str = OPENAI_API_KEY):
        self.eleven_client = ElevenLabsClient(api_key=eleven_key)
        self.openai_client = OpenAI(api_key=openai_key)

    def generate_briefing_script(self, intelligence: Dict[str, Any], user_profile: Optional[Dict[str, Any]] = None) -> str:
        """Generates high-impact spoken audio script for ElevenLabs narration."""
        title = intelligence.get("meeting_title", "Reunião Executiva")
        summary = intelligence.get("executive_summary", "")
        commitments = intelligence.get("commitments_and_promises", [])
        accounts = intelligence.get("accounts_discussed", [])

        voice_style = (user_profile or {}).get("preferred_voice_tone", "Executivo Direto e Sofisticado")
        user_name = (user_profile or {}).get("user_name", "Felipe")

        prompt = f"""Você é o narrador executivo do Jarvis Voice OS.
Gere um roteiro de áudio falado de exatamente 60 a 75 segundos em tom {voice_style} para o executivo {user_name}.

Diretrizes de Roteiro Falado:
- Comece direto e enérgico: "Fala {user_name}, aqui está o seu briefing executivo da reunião..."
- Resuma as 2 principais decisões em linguagem natural e falada.
- Destaque os compromissos imediatos que ele precisa cumprir hoje.
- Termine com uma frase de foco e alta performance.
- NÃO use bullet points, asteriscos ou emojis no texto, apenas prosa fluida pontuada para fala natural.

Dados da Reunião:
Título: {title}
Resumo: {summary}
Compromissos: {json.dumps(commitments, ensure_ascii=False)}
Contas: {json.dumps(accounts, ensure_ascii=False)}
"""

        response = self.openai_client.chat.completions.create(
            model="gpt-4o",
            temperature=0.4,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()

    def create_audio_briefing(self, file_id: str, intelligence: Dict[str, Any], user_profile: Optional[Dict[str, Any]] = None) -> Optional[Path]:
        """Generates script and synthesizes MP3 via ElevenLabs."""
        output_file = AUDIO_BRIEFING_DIR / f"{file_id}_briefing.mp3"
        if output_file.exists() and output_file.stat().st_size > 1000:
            logging.info(f"Audio briefing already exists: {output_file}")
            return output_file

        logging.info("Generating executive audio briefing script...")
        script = self.generate_briefing_script(intelligence, user_profile)
        logging.info(f"Script generated ({len(script)} chars): {script[:100]}...")

        # Save text script
        script_file = AUDIO_BRIEFING_DIR / f"{file_id}_script.txt"
        with open(script_file, "w", encoding="utf-8") as f:
            f.write(script)

        # Select Voice ID
        voice_id = (user_profile or {}).get("elevenlabs_voice_id", DEFAULT_VOICES.get("jarvis", "JBFqnCBsd6RMkjVDRZzb"))

        logging.info(f"Synthesizing audio via ElevenLabs (Voice: {voice_id})...")
        if self.eleven_client.is_configured():
            audio_bytes = self.eleven_client.text_to_speech(
                text=script,
                voice_id=voice_id,
                model_id="eleven_multilingual_v2"
            )
            if audio_bytes:
                with open(output_file, "wb") as f:
                    f.write(audio_bytes)
                logging.info(f"🎉 Audio briefing generated successfully: {output_file} ({len(audio_bytes)} bytes)")
                return output_file
        
        # Fallback to OpenAI TTS if ElevenLabs key is not set or throttled
        logging.warning("ElevenLabs not active or failed; using OpenAI TTS HD fallback...")
        try:
            response = self.openai_client.audio.speech.create(
                model="tts-1-hd",
                voice="onyx",
                input=script
            )
            response.stream_to_file(str(output_file))
            logging.info(f"🎉 Audio briefing generated with OpenAI TTS: {output_file}")
            return output_file
        except Exception as e:
            logging.error(f"Failed to generate audio briefing: {e}")
            return None

if __name__ == "__main__":
    v = VoiceBriefingEngine()
    print("VoiceBriefingEngine ready.")
