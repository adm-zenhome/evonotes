import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from openai import OpenAI

from .config import DATA_DIR, OPENAI_API_KEY

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

PROFILES_DIR = DATA_DIR / "profiles"
PROFILES_DIR.mkdir(parents=True, exist_ok=True)

class SelfLearningEngine:
    """Autonomous per-user profile learning, jargon extraction, and style calibration system."""

    def __init__(self, openai_key: str = OPENAI_API_KEY):
        self.openai_client = OpenAI(api_key=openai_key)
        self.profiles_dir = PROFILES_DIR

    def get_or_create_profile(self, user_id: str = "felipe_donato") -> Dict[str, Any]:
        """Loads isolated user profile or initializes a clean one."""
        profile_file = self.profiles_dir / f"{user_id}.json"
        if profile_file.exists():
            try:
                with open(profile_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logging.error(f"Error loading profile {user_id}: {e}")

        default_profile = {
            "user_id": user_id,
            "user_name": "Felipe Donato" if user_id == "felipe_donato" else "Executivo",
            "company": "Zendesk",
            "preferred_voice_tone": "Executivo Direto, Confiante e Sofisticado",
            "elevenlabs_voice_id": "JBFqnCBsd6RMkjVDRZzb", # Jarvis / George
            "calibration_meetings_processed": 0,
            "calibration_target": 10,
            "calibration_status": "LEARNING", # LEARNING | CALIBRATED
            "vocabulary_and_jargon": ["ZCC", "ASW", "ARs", "Resell", "Deal Size", "Finder's Fee", "Diarização"],
            "stakeholders": [
                {"name": "Dani", "role": "Diretora / Zendesk", "relationship": "Liderança Direta"},
                {"name": "Valéria", "role": "Enterprise AE / Zendesk", "relationship": "Parceira Interna"},
                {"name": "Mineiro", "role": "Enterprise AE / Zendesk", "relationship": "Parceiro Interno"},
                {"name": "Bruno Rodrigues", "role": "CEO / BCR", "relationship": "Parceiro Estratégico"},
                {"name": "Felipe Bastos", "role": "Executivo / BCR", "relationship": "Parceiro Estratégico"},
                {"name": "Caio", "role": "Especialista ZX / Zendesk", "relationship": "Time Técnico"},
                {"name": "Max", "role": "Cliente / Blue3", "relationship": "Prospect / Cliente"}
            ],
            "style_preferences": {
                "bullet_format": "Conciso e orientado a decisões",
                "email_tone": "Profissional, elegante, focado em próximos passos",
                "risk_sensitivity": "ALTA"
            },
            "learned_insights": [
                "Felipe prioriza agilidade de fechamento e proteção de margem/preço.",
                "Prefere resumos em tópicos diretos e matriz clara de compromissos."
            ],
            "last_updated": datetime.now().isoformat()
        }
        self.save_profile(user_id, default_profile)
        return default_profile

    def save_profile(self, user_id: str, profile_data: Dict[str, Any]):
        """Saves isolated profile strictly in tenant profile file."""
        profile_file = self.profiles_dir / f"{user_id}.json"
        profile_data["last_updated"] = datetime.now().isoformat()
        with open(profile_file, "w", encoding="utf-8") as f:
            json.dump(profile_data, f, indent=2, ensure_ascii=False)
        logging.info(f"User profile {user_id} saved.")

    def calibrate_from_meeting(self, user_id: str, transcript_text: str, intelligence: Dict[str, Any]) -> Dict[str, Any]:
        """Analyzes a new meeting to autonomously refine the user profile."""
        profile = self.get_or_create_profile(user_id)
        current_count = profile.get("calibration_meetings_processed", 0) + 1
        profile["calibration_meetings_processed"] = current_count

        if current_count >= profile.get("calibration_target", 10):
            profile["calibration_status"] = "CALIBRATED"

        logging.info(f"Calibrating user {user_id} (Meeting {current_count}/{profile['calibration_target']})...")

        prompt = f"""Você é o Motor de Auto-Aprimoramento do Jarvis Voice OS.
Analise a nova reunião processada e atualize o Perfil de Aprendizado do Usuário.

Perfil Atual:
{json.dumps(profile, ensure_ascii=False, indent=2)}

Nova Reunião:
Título: {intelligence.get('meeting_title')}
Participantes: {json.dumps(intelligence.get('participants', []), ensure_ascii=False)}
Contas: {json.dumps(intelligence.get('accounts_discussed', []), ensure_ascii=False)}
Resumo: {intelligence.get('executive_summary')}

Instruções de Calibração:
1. Extraia novos jargões, termos técnicos ou siglas que apareceram e adicione à lista (sem duplicatas).
2. Adicione novos stakeholders/participantes identificados com seus respectivos papéis.
3. Extraia 1 ou 2 novos insights sobre o estilo de trabalho e prioridades do executivo.
4. Mantenha os dados existentes e apenas enriqueça a base.

Retorne o JSON atualizado com as chaves: vocabulary_and_jargon, stakeholders, learned_insights."""

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                temperature=0.2,
                response_format={"type": "json_object"},
                messages=[{"role": "user", "content": prompt}]
            )
            updates = json.loads(response.choices[0].message.content)
            
            if "vocabulary_and_jargon" in updates:
                profile["vocabulary_and_jargon"] = updates["vocabulary_and_jargon"]
            if "stakeholders" in updates:
                profile["stakeholders"] = updates["stakeholders"]
            if "learned_insights" in updates:
                profile["learned_insights"] = updates["learned_insights"]

            self.save_profile(user_id, profile)
            logging.info(f"Profile calibration complete for {user_id} ({current_count}/10).")
        except Exception as e:
            logging.error(f"Error during self-learning calibration: {e}")

        return profile

    def build_prompt_injection(self, user_id: str = "felipe_donato") -> str:
        """Builds context injection for IntelligenceEngine based on calibrated profile."""
        p = self.get_or_create_profile(user_id)
        return f"""
--- CONTEXTO CALIBRADO DO EXECUTIVO ({p.get('user_name')}) ---
Status de Calibração: {p.get('calibration_status')} ({p.get('calibration_meetings_processed')}/{p.get('calibration_target')} reuniões aprendidas)
Jargões e Siglas Recorrentes: {', '.join(p.get('vocabulary_and_jargon', []))}
Diretório de Pessoas Chave: {json.dumps(p.get('stakeholders', []), ensure_ascii=False)}
Preferências de Estilo: {json.dumps(p.get('style_preferences', {}), ensure_ascii=False)}
Insights de Trabalho: {'; '.join(p.get('learned_insights', []))}
------------------------------------------------------------
"""

if __name__ == "__main__":
    sle = SelfLearningEngine()
    prof = sle.get_or_create_profile("felipe_donato")
    print(f"Profile loaded: {prof['user_name']} - Status: {prof['calibration_status']} ({prof['calibration_meetings_processed']}/10)")
