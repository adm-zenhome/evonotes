import os
import json
import logging
from typing import Dict, Any, Optional
from openai import OpenAI
from .config import OPENAI_API_KEY
from .self_learning_engine import SelfLearningEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

EXECUTIVE_SYSTEM_PROMPT = """Você é o Jarvis Executive Voice Intelligence Engine — o Chief of Staff e Diretor de Revenue Intelligence.

Sua missão é transformar transcrições de áudios brutos de reuniões em inteligência acionável de altíssimo nível executivo (C-Level).

Diretrizes de Título e Nomenclatura Contextual:
- Crie um título memorável, direto e com emoji no formato:
  `[🏢 Empresa(s) / Parceiro] — [💡 Tema Principal / Objetivo Central]`
- Crie um teaser de 1 linha e uma lista de 2 a 4 tags.

Diretrizes Críticas de Inteligência:
1. **Fidelidade Absoluta:** Nunca invente dados, nomes ou números que não estejam no áudio.
2. **Diarização & Identificação de Papéis:** Separe com clareza quem é time interno, quem é parceiro e quem é cliente.
3. **Auditoria de Promessas & To-Dos:** Extraia TODO compromisso verbal feito.
4. **Inteligência de Vendas (MEDDIC / BANT):** Mapeie contas citadas, dores, concorrentes, tese comercial e próximos passos.
5. **Rascunho de E-mail de Follow-up:** Gere rascunho de e-mail pronto para envio imediato aos participantes.

Estrutura de Saída (JSON Válido Obrigatório):
{
  "meeting_title": "🏢 Nome Contextual da Reunião",
  "teaser": "Resumo de 1 linha para exibição rápida na sidebar",
  "tags": ["Tag1", "Tag2", "Tag3"],
  "category": "Comercial / Pipeline / Estratégia / Pessoal",
  "executive_summary": "Resumo de 3 a 5 parágrafos com as decisões e rumos tomados.",
  "participants": [
    {"name": "Nome", "role": "Papel / Empresa", "key_stance": "Posicionamento principal na reunião"}
  ],
  "commitments_and_promises": [
    {"owner": "Nome", "action": "Ação específica prometida", "deadline_or_context": "Contexto ou prazo", "urgency": "ALTA / MEDIA / BAIXA"}
  ],
  "accounts_discussed": [
    {"account_name": "Nome da Conta", "current_situation": "Situação atual", "opportunity_or_risk": "Oportunidade/Risco", "next_step": "Próximo passo"}
  ],
  "strategic_theses": [
    "Teses de vendas ou posicionamento de mercado levantadas"
  ],
  "follow_up_emails": [
    {"to": "Destinatário(s)", "subject": "Assunto do E-mail", "body": "Corpo do e-mail em formato profissional pronto para envio"}
  ],
  "key_highlights": [
    "Destaques marcantes ou citações relevantes"
  ]
}
"""

import re

VOCABULARY_CORRECTIONS = [
    (r"\bActian\b", "Aktie Now"),
    (r"\bAktienow\b", "Aktie Now"),
    (r"\bActie\s+Now\b", "Aktie Now"),
    (r"\bNaga\b", "Vonage"),
    (r"\bNaj[aá]\b", "Vonage"),
    (r"\bMandique\b", "Mantiqueira"),
    (r"\bMantique\b", "Mantiqueira"),
    (r"\bPCR\b", "BCR"),
    (r"\bBlue\s*3\b", "Blue3"),
    (r"\bZCC\b", "ZCC (Zendesk Contact Center)"),
]

def normalize_text_vocabulary(text: str) -> str:
    """Deterministically normalizes acoustic speech-to-text mishearings to accurate corporate entities."""
    if not text:
        return ""
    normalized = text
    for pattern, replacement in VOCABULARY_CORRECTIONS:
        normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
    return normalized

class IntelligenceEngine:
    """Extracts executive intelligence, commitments, deal strategy and follow-ups from transcripts."""

    def __init__(self, api_key: str = OPENAI_API_KEY):
        self.client = OpenAI(api_key=api_key)
        self.learning_engine = SelfLearningEngine(openai_key=api_key)

    def analyze(self, transcript_text: str, metadata: Optional[Dict[str, Any]] = None, user_id: str = "felipe_donato") -> Dict[str, Any]:
        """Analyzes full transcript using LLM with learned user profile injection."""
        logging.info(f"Running executive intelligence analysis for user: {user_id}...")

        # Pre-normalize acoustic transcript errors
        clean_transcript = normalize_text_vocabulary(transcript_text)

        context_info = ""
        if metadata:
            context_info = f"\nMetadados da gravação: {json.dumps(metadata, ensure_ascii=False)}\n"

        # Injetar aprendizado do usuário
        user_context = self.learning_engine.build_prompt_injection(user_id)

        prompt = f"""Analise a seguinte transcrição de áudio e extraia a inteligência completa no formato JSON especificado.
Certifique-se de usar a nomenclatura corporativa correta (ex: Aktie Now, BCR, Mantiqueira, Blue3, Vonage).

{user_context}

{context_info}
--- TRANSCRIÇÃO COMPLETA ---
{clean_transcript}
--- FIM DA TRANSCRIÇÃO ---
"""

        response = self.client.chat.completions.create(
            model="gpt-4o",
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": EXECUTIVE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]
        )

        raw_json = response.choices[0].message.content
        try:
            # Post-process vocabulary in json
            cleaned_json = normalize_text_vocabulary(raw_json)
            structured_data = json.loads(cleaned_json)
            logging.info("Intelligence extraction successful.")
            
            # Calibrate user profile from this meeting
            try:
                self.learning_engine.calibrate_from_meeting(user_id, clean_transcript, structured_data)
            except Exception as e:
                logging.error(f"Error updating self-learning profile: {e}")

            return structured_data
        except Exception as e:
            logging.error(f"Failed to parse JSON: {e}")
            return {"error": str(e), "raw_response": raw_json}

if __name__ == "__main__":
    engine = IntelligenceEngine()
    print("IntelligenceEngine with SelfLearning ready.")
