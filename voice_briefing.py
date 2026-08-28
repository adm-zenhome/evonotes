import os
import json
import logging
from pathlib import Path
from datetime import datetime
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
        """Generates high-impact spoken audio script structured in 3 Pillars: Pontos de Atenção, Detalhes Percebidos e Próximos Passos."""
        title = intelligence.get("meeting_title", "Reunião Executiva")
        summary = intelligence.get("executive_summary", "")
        commitments = intelligence.get("commitments_and_promises", [])
        accounts = intelligence.get("accounts_discussed", [])

        voice_style = (user_profile or {}).get("preferred_voice_tone", "Executivo Direto, Estratégico e Sofisticado")
        user_name = (user_profile or {}).get("user_name", "Felipe")

        prompt = f"""Você é o Narrador Executivo de Inteligência do EvoNotes OS.
Gere um roteiro de áudio falado de exatamente 60 a 80 segundos em tom {voice_style} para o executivo {user_name}.

ESTRUTURA OBRIGATÓRIA DO ÁUDIO NARRADO (3 PILARES):
1. ABERTURA & PONTOS DE ATENÇÃO:
   - Comece direto: "Fala {user_name}, briefing executivo de {title}..."
   - Aponte imediatamente o principal PONTO DE ATENÇÃO ou risco de fechamento/concorrência identificado na conversa.
2. DETALHES & NUANCES PERCEBIDAS:
   - Destaque o que foi percebido nas entrelinhas (postura dos decisores, menções a concorrentes como Aktie Now, modelo de pricing FNR ou objeções de telefonia ZCC).
3. PRÓXIMOS PASSOS & DONOS:
   - Dicte com clareza cirúrgica as 2 ou 3 ações imediatas com seus respectivos donos e prazos combinados.
   - Encerramento de alta performance.

REGRAS DE FORMATAÇÃO DE VOZ:
- Texto 100% corrido e pontuado para fala fluida humana.
- PROIBIDO usar bullet points, números soltos, asteriscos ou emojis no texto.

DADOS DA REUNIÃO:
Título: {title}
Resumo: {summary}
Compromissos: {json.dumps(commitments, ensure_ascii=False)}
Contas e Deals: {json.dumps(accounts, ensure_ascii=False)}
"""

        response = self.openai_client.chat.completions.create(
            model="gpt-4o",
            temperature=0.4,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()

def create_audio_briefing(self, file_id: str, intelligence: Dict[str, Any], user_profile: Optional[Dict[str, Any]] = None, force_new_take: bool = False) -> Optional[Path]:
        """Generates script and synthesizes MP3 via ElevenLabs, preserving historical versions."""
        versions_file = AUDIO_BRIEFING_DIR / f"{file_id}_versions.json"
        versions = []
        if versions_file.exists():
            try:
                with open(versions_file, "r", encoding="utf-8") as f:
                    versions = json.load(f)
            except Exception:
                versions = []

        output_file = AUDIO_BRIEFING_DIR / f"{file_id}_briefing.mp3"

        # If audio already exists and not forced, return existing
        if output_file.exists() and output_file.stat().st_size > 1000 and not force_new_take:
            logging.info(f"Audio briefing already exists: {output_file}")
            return output_file

        # If forcing new take, archive the existing audio as v1, v2, etc.
        if output_file.exists() and force_new_take:
            v_num = len(versions) + 1
            archived_file = AUDIO_BRIEFING_DIR / f"{file_id}_briefing_v{v_num}.mp3"
            try:
                import shutil
                shutil.copy2(output_file, archived_file)
                if not any(v.get("version") == v_num for v in versions):
                    versions.append({
                        "version": v_num,
                        "filename": archived_file.name,
                        "created_at": datetime.now().strftime("%d/%m %H:%M"),
                        "url": f"/api/audio-briefing/{file_id}?v={v_num}"
                    })
            except Exception as e:
                logging.error(f"Error archiving version {v_num}: {e}")

        logging.info("Generating executive audio briefing script with ElevenLabs...")
        script = self.generate_briefing_script(intelligence, user_profile)
        logging.info(f"Script generated ({len(script)} chars): {script[:100]}...")

        # Save text script
        script_file = AUDIO_BRIEFING_DIR / f"{file_id}_script.txt"
        with open(script_file, "w", encoding="utf-8") as f:
            f.write(script)

        # Synthesize audio with ElevenLabs
        voice_id = (user_profile or {}).get("elevenlabs_voice_id", "JBFqnCBsd6RMkjVDRZzb")
        audio_bytes = self.eleven_client.text_to_speech(script, voice_id=voice_id)

        if audio_bytes:
            with open(output_file, "wb") as f:
                f.write(audio_bytes)
            
            # Register new current version
            latest_v = len(versions) + 1
            latest_archived = AUDIO_BRIEFING_DIR / f"{file_id}_briefing_v{latest_v}.mp3"
            with open(latest_archived, "wb") as f:
                f.write(audio_bytes)

            versions.append({
                "version": latest_v,
                "filename": latest_archived.name,
                "created_at": datetime.now().strftime("%d/%m %H:%M"),
                "url": f"/api/audio-briefing/{file_id}?v={latest_v}",
                "is_latest": True
            })

            with open(versions_file, "w", encoding="utf-8") as f:
                json.dump(versions, f, indent=2, ensure_ascii=False)

            logging.info(f"Executive audio briefing saved successfully: {output_file} (Version {latest_v})")
            return output_file
        else:
            logging.error("Failed to generate ElevenLabs audio bytes")
            return None

if __name__ == "__main__":
    v = VoiceBriefingEngine()
    print("VoiceBriefingEngine ready.")
