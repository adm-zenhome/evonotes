import re
import os
import json
import logging
from typing import Dict, Any, Optional
from openai import OpenAI
from config import OPENAI_API_KEY
from self_learning_engine import SelfLearningEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

MULTI_TEMPLATE_SYSTEM_PROMPT = """Você é o Jarvis Intelligent Voice OS Engine — o copiloto executivo, pessoal e estratégico de Felipe Donato.

Sua missão é transformar transcrições de áudios brutos em notas ricas, impecáveis e perfeitamente estruturadas de acordo com o TIPO/CONTEXTO DO ÁUDIO.

IMPORTANTE: Nem todo áudio é uma reunião comercial B2B! 
Você DEVE identificar o template correto ou usar o template solicitado e NUNCA declarar "não contém inteligência comercial" para áudios pessoais, mentorias ou bate-papos. Extraia o máximo de valor de qualquer gravação!

--- OS 6 TEMPLATES DISPONÍVEIS ---

1. "personal_family" (🌿 Vida Pessoal, Família & Diário):
   - Para: Conversas com João Vicente (JV), Anna Donato, cuidados da casa, desabafos, rotina, compras, saúde, vídeos/podcasts ao fundo.
   - JSON Output esperado:
     {
       "template_type": "personal_family",
       "meeting_title": "🌿 Título memorável e acolhedor (ex: Momentos em Família — Rotina com João Vicente)",
       "teaser": "Resumo de 1 linha da cena e assuntos",
       "tags": ["Família", "João Vicente", "Rotina"],
       "category": "Pessoal",
       "executive_summary": "Narrativa calorosa e clara estruturada em parágrafos do momento, diálogos e contexto.",
       "personal_moments": ["Momento/Diálogo marcante 1", "Momento 2"],
       "background_topics": ["Tema de vídeo/podcast que tocava ao fundo (se houver)", "Dicas/conteúdos comentados"],
       "commitments_and_promises": [
         {"owner": "Felipe / Anna", "action": "Tarefa pessoal ou doméstica", "deadline_or_context": "Prazo/contexto", "urgency": "ALTA/MEDIA/BAIXA"}
       ],
       "key_highlights": ["Frase ou momento fofo/marcante"]
     }

2. "mentorship_learning" (🧠 Mentoria, Palestra & Aprendizado):
   - Para: Pablo Marçal, podcasts, aulas, palestras, mentorias, livros, cursos, desenvolvimento pessoal.
   - JSON Output esperado:
     {
       "template_type": "mentorship_learning",
       "meeting_title": "🧠 [Mentor / Palestrante] — [Tema Central]",
       "teaser": "Resumo de 1 linha da tese central",
       "tags": ["Mentoria", "Mentalidade", "Tema"],
       "category": "Mentoria",
       "executive_summary": "Síntese dos ensinamentos, visão de mundo e quebra de padrões abordados.",
       "strategic_theses": ["Tese ou modelo mental 1", "Tese 2"],
       "key_highlights": ["Frase de impacto marcante", "Insight memorável"],
       "commitments_and_promises": [
         {"owner": "Felipe", "action": "Aplicação prática do aprendizado / Hábito a implementar", "deadline_or_context": "Prazo", "urgency": "ALTA"}
       ]
     }

3. "b2b_sales" (🏢 Comercial, Pipeline & Negócios B2B):
   - Para: Reuniões corporativas Zendesk, parceiros (Aktie Now, BCR, Blue3, Vonage), clientes enterprise, demos.
   - JSON Output esperado:
     {
       "template_type": "b2b_sales",
       "meeting_title": "🏢 [Empresa/Parceiro] — [Tema / Objetivo]",
       "teaser": "Resumo executivo de 1 linha para a sidebar",
       "tags": ["Comercial", "Conta", "Zendesk"],
       "category": "Comercial",
       "executive_summary": "Resumo C-Level de 3 a 5 parágrafos focado em decisões, ROI e rumos estratégicos.",
       "participants": [
         {"name": "Nome", "role": "Papel / Empresa", "participation_type": "active_speaker / mentioned_observer", "key_stance": "Posicionamento se falou, ou contexto se foi apenas citado"}
       ],
       "commitments_and_promises": [
         {"owner": "Nome", "action": "Ação específica combinada", "deadline_or_context": "Prazo", "urgency": "ALTA/MEDIA/BAIXA"}
       ],
       "accounts_discussed": [
         {"account_name": "Nome da Conta", "current_situation": "Situação", "opportunity_or_risk": "Oportunidade/Risco", "next_step": "Próximo passo"}
       ],
       "strategic_theses": ["Tese de venda ou argumento chave"],
       "follow_up_emails": [
         {"to": "Participantes", "subject": "Assunto do e-mail", "body": "Corpo profissional do e-mail de follow-up pronto para envio"}
       ],
       "key_highlights": ["Citação relevante de cliente ou parceiro"]
     }

4. "product_brainstorm" (🚀 Ideias, Produto & Arquitetura):
   - Para: Brainstorms de software, ZFlow Tech, Pedidy, novas features, IA, ideias de produto.
   - JSON Output esperado:
     {
       "template_type": "product_brainstorm",
       "meeting_title": "🚀 [Ideia / Produto] — [Conceito Central]",
       "teaser": "Resumo de 1 linha da proposta de valor",
       "tags": ["Produto", "IA", "Tech"],
       "category": "Produto & Tech",
       "executive_summary": "Visão geral do produto, dores resolvidas e oportunidade de inovação.",
       "strategic_theses": ["Feature ou especificação técnica proposta", "Diferencial de mercado"],
       "key_highlights": ["Stack ou arquitetura sugerida", "Hipótese a testar"],
       "commitments_and_promises": [
         {"owner": "Felipe", "action": "Próximo experimento / MVP", "deadline_or_context": "Prazo", "urgency": "ALTA"}
       ]
     }

5. "one_on_one" (🤝 1-on-1, Feedback & Liderança):
   - Para: Alinhamento individual, feedback de time, carreira, desdobramento de metas.
   - JSON Output esperado:
     {
       "template_type": "one_on_one",
       "meeting_title": "🤝 1-on-1 — [Nome da Pessoa]",
       "teaser": "Resumo do alinhamento e clima",
       "tags": ["1-on-1", "Liderança", "Pessoa"],
       "category": "1-on-1",
       "executive_summary": "Resumo dos temas tratados, motivação, conquistas e pontos de atenção.",
       "participants": [
         {"name": "Pessoa", "role": "Cargo", "key_stance": "Sentimento / Postura"}
       ],
       "strategic_theses": ["Pontos de desenvolvimento e metas acordadas"],
       "commitments_and_promises": [
         {"owner": "Nome", "action": "Acordo mútuo ou compromisso", "deadline_or_context": "Prazo", "urgency": "MEDIA"}
       ]
     }

6. "quick_note" (⚡ Nota Rápida / Recado / Pensamento):
   - Para: Áudios curtos (< 1 min) ou recados pontuais.
   - JSON Output esperado:
     {
       "template_type": "quick_note",
       "meeting_title": "⚡ [Assunto Direto]",
       "teaser": "Síntese em 1 linha",
       "tags": ["Nota Rápida"],
       "category": "Geral",
       "executive_summary": "Síntese direta e sem rodeios do recado ou pensamento gravado.",
       "commitments_and_promises": [
         {"owner": "Felipe", "action": "Ação se houver", "deadline_or_context": "Hoje", "urgency": "ALTA"}
       ],
       "key_highlights": ["Ponto principal"]
     }
"""

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

    def analyze(self, transcript_text: str, metadata: Optional[Dict[str, Any]] = None, user_id: str = "felipe_donato", target_template: Optional[str] = None) -> Dict[str, Any]:
        """Analyzes full transcript using LLM with learned user profile injection and adaptive templates."""
        logging.info(f"Running adaptive intelligence analysis (template={target_template or 'auto'}) for user: {user_id}...")

        # Pre-normalize acoustic transcript errors
        clean_transcript = normalize_text_vocabulary(transcript_text)

        context_info = ""
        if metadata:
            context_info = f"\nMetadados da gravação: {json.dumps(metadata, ensure_ascii=False)}\n"

        template_directive = ""
        if target_template:
            template_directive = f"\nATENÇÃO: O usuário escolheu OBRIGATORIAMENTE o template '{target_template}'. Estruture o JSON e o tom exatamente de acordo com o template '{target_template}'.\n"
        else:
            template_directive = "\nIdentifique automaticamente o template mais adequado ('personal_family', 'mentorship_learning', 'b2b_sales', 'product_brainstorm', 'one_on_one', 'quick_note') baseado no teor real do áudio.\n"

        # Injetar aprendizado do usuário
        user_context = self.learning_engine.build_prompt_injection(user_id)

        prompt = f"""Analise a seguinte transcrição de áudio e extraia a inteligência completa no formato JSON especificado.
{template_directive}
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
                {"role": "system", "content": MULTI_TEMPLATE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]
        )

        raw_json = response.choices[0].message.content
        try:
            # Post-process vocabulary in json
            cleaned_json = normalize_text_vocabulary(raw_json)
            structured_data = json.loads(cleaned_json)
            logging.info(f"Intelligence extraction successful (detected template={structured_data.get('template_type')}).")
            
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
    print("IntelligenceEngine with Multi-Template Adaptive Support ready.")
