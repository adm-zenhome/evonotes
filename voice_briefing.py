import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from openai import OpenAI

from config import OPENAI_API_KEY, CACHE_DIR
from eleven_client import ElevenLabsClient, DEFAULT_VOICES

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

AUDIO_BRIEFING_DIR = CACHE_DIR / "audio_briefings"
AUDIO_BRIEFING_DIR.mkdir(parents=True, exist_ok=True)

class VoiceBriefingEngine:
    """Generates 60-90s executive audio podcast briefings via ElevenLabs."""

    def __init__(self, eleven_key: Optional[str] = None, openai_key: str = OPENAI_API_KEY):
        self.eleven_client = ElevenLabsClient(api_key=eleven_key)
        self.openai_client = OpenAI(api_key=openai_key or os.environ.get("OPENAI_API_KEY") or "sk-dummy-startup-key")

    def generate_briefing_script(self, intelligence: Dict[str, Any], user_profile: Optional[Dict[str, Any]] = None, custom_direction: Optional[str] = None) -> str:
        """Generates high-impact spoken audio script structured in 3 Pillars, with optional executive customization."""
        title = intelligence.get("meeting_title", "Reunião Executiva")
        summary = intelligence.get("executive_summary", "")
        commitments = intelligence.get("commitments_and_promises", [])
        accounts = intelligence.get("accounts_discussed", [])

        voice_style = (user_profile or {}).get("preferred_voice_tone", "Executivo Direto, Estratégico e Sofisticado")
        user_name = (user_profile or {}).get("user_name", "Felipe")

        custom_block = f"""
DIRETRIZ PRIORITÁRIA DO EXECUTIVO (MOLDE O ÁUDIO COM ESTE FOCO):
{custom_direction}
""" if custom_direction else ""

        prompt = f"""Você é o Narrador Executivo de Inteligência do EvoNotes OS.
Gere um roteiro de áudio falado de exatamente 60 a 80 segundos em tom {voice_style} para o executivo {user_name}.
{custom_block}
ESTRUTURA OBRIGATÓRIA DO ÁUDIO NARRADO:
1. ABERTURA & PONTOS DE ATENÇÃO:
   - Comece direto: "Fala {user_name}, briefing executivo de {title}..."
   - Aponte imediatamente o principal PONTO DE ATENÇÃO ou risco de fechamento/concorrência identificado na conversa.
2. DETALHES & NUANCES PERCEBIDAS:
   - Destaque o que foi percebido nas entrelinhas (postura dos decisores, menções a concorrentes, modelo de pricing FNR ou objeções de telefonia ZCC).
3. PRÓXIMOS PASSOS & DONOS:
   - Dicte com clareza cirúrgica as ações imediatas com seus respectivos donos e prazos combinados.
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

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                temperature=0.4,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logging.warning(f"OpenAI script generation error ({e}), generating deterministic script fallback.")
            first_action = commitments[0].get('action', 'Avançar com alinhamentos') if commitments else 'Revisar itens da reunião'
            return f"Fala {user_name}, briefing executivo de {title}. Principais decisões alinhadas: {summary[:200]}. Próximo passo prioritário: {first_action}. Todas as diretrizes estão salvas no EvoNotes."

    def create_audio_briefing(self, file_id: str, intelligence: Dict[str, Any], user_profile: Optional[Dict[str, Any]] = None, force_new_take: bool = False, custom_direction: Optional[str] = None) -> Optional[Path]:
        """Generates script and synthesizes MP3 via ElevenLabs/OpenAI, preserving historical versions."""
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
                        "url": f"/api/audio-briefing/{file_id}?v={v_num}",
                        "direction": custom_direction or "Padrão (3 Pilares)"
                    })
            except Exception as e:
                logging.error(f"Error archiving version {v_num}: {e}")

        logging.info(f"Generating executive audio briefing script (Custom Direction: {custom_direction})...")
        script = self.generate_briefing_script(intelligence, user_profile, custom_direction=custom_direction)
        logging.info(f"Script generated ({len(script)} chars): {script[:100]}...")

        # Save text script
        script_file = AUDIO_BRIEFING_DIR / f"{file_id}_script.txt"
        with open(script_file, "w", encoding="utf-8") as f:
            f.write(script)

        # Synthesize audio with ElevenLabs (or fallback to OpenAI TTS HD or macOS local)
        voice_id = (user_profile or {}).get("elevenlabs_voice_id", "JBFqnCBsd6RMkjVDRZzb")
        audio_bytes = None
        try:
            audio_bytes = self.eleven_client.text_to_speech(text=script, voice_id=voice_id)
        except Exception as e1:
            logging.warning(f"ElevenLabs synthesis error, falling back to OpenAI TTS HD: {e1}")
            try:
                tts_res = self.openai_client.audio.speech.create(
                    model="tts-1-hd",
                    voice="onyx",
                    input=script
                )
                audio_bytes = tts_res.content
            except Exception as e2:
                logging.warning(f"OpenAI TTS error, falling back to macOS local TTS: {e2}")
                import subprocess, tempfile
                with tempfile.NamedTemporaryFile(suffix=".aiff", delete=False) as tf:
                    temp_aiff = tf.name
                subprocess.run(["say", "-v", "Luciana", "-o", temp_aiff, script[:500]], check=False)
                if Path(temp_aiff).exists():
                    subprocess.run(["ffmpeg", "-y", "-i", temp_aiff, "-codec:a", "libmp3lame", "-qscale:a", "2", str(output_file)], check=False)
                    try:
                        os.remove(temp_aiff)
                    except Exception:
                        pass
                if output_file.exists():
                    audio_bytes = output_file.read_bytes()

        if audio_bytes:
            with open(output_file, "wb") as f:
                f.write(audio_bytes)

        # Update latest take in versions json
        versions.append({
            "version": len(versions) + 1,
            "filename": output_file.name,
            "created_at": "Take Atual",
            "url": f"/api/audio-briefing/{file_id}",
            "direction": custom_direction or "Padrão (3 Pilares)"
        })
        with open(versions_file, "w", encoding="utf-8") as f:
            json.dump(versions, f, ensure_ascii=False, indent=2)

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
