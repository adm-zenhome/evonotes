import os
import re
import json
import logging
from typing import Dict, Any, Optional, List
from openai import OpenAI

try:
    from .config import OPENAI_API_KEY
    from .self_learning_engine import SelfLearningEngine
    from .vocabulary_engine import AcousticVocabularyEngine, default_vocab_engine
except (ImportError, ValueError):
    from config import OPENAI_API_KEY
    from self_learning_engine import SelfLearningEngine
    from vocabulary_engine import AcousticVocabularyEngine, default_vocab_engine

logger = logging.getLogger("intelligence_engine")
logger.setLevel(logging.INFO)

# --- 7 ADAPTIVE TEMPLATES & SYSTEM PROMPTS ---

PROFESSION_PROMPT_SPECIALIZATIONS = {
    "general": """Você é o EvoNotes Executive Intelligence Engine — copiloto executivo agnóstico e segundo cérebro.
Foco: Decisões tomadas, compromissos com prazos, prioridades estratégicas e síntese clara sem jargões corporativos forçados.""",
    
    "sales": """Você é o EvoNotes B2B Revenue Intelligence Engine — especialista em vendas consultivas, negociação e pipeline corporativo.
Foco: Mapeamento de contas, decisores (stakeholders), dores e objeções, qualificação de oportunidade (BANT/MEDDIC), pricing e próximos passos de fechamento.""",
    
    "health": """Você é o EvoNotes Clinical Scribe & Medical Intelligence Engine — especialista em escuta clínica e síntese médica.
Foco: Anamnese detalhada, queixa principal (HDA), sintomas descritos, hipóteses diagnósticas, exames solicitados e condutas/prescrições com posologias claras.""",
    
    "legal": """Você é o EvoNotes Legal Intelligence Engine — especialista em direito e prática jurídica.
Foco: Audiências, reuniões com clientes, teses e fundamentos jurídicos, prazos processuais fatais, partes envolvidas, documentos pendentes e acordos celebrados.""",
    
    "tech": """Você é o EvoNotes Engineering & Tech Architecture Intelligence Engine — especialista em tecnologia e produto.
Foco: Decisões de arquitetura (ADRs/RFCs), débitos técnicos, especificações de features, bugs e incidentes, releases e sprints.""",
    
    "consulting": """Você é o EvoNotes Strategy Consulting Intelligence Engine — especialista em diagnóstico e gestão de projetos.
Foco: Diagnóstico situacional, metodologias aplicadas, entregáveis e marcos (milestones), roadmap de implementação e plano de ação estruturado."""
}

MULTI_TEMPLATE_SYSTEM_PROMPT = """Você é o Intelligent Voice OS Engine — copiloto executivo, pessoal e estratégico de inteligência em áudio.

Sua missão é transformar transcrições de áudios brutos e notas humanas em resumos impecáveis e perfeitamente estruturados em JSON de acordo com o TIPO/CONTEXTO DO ÁUDIO e a ESPECIALIZAÇÃO DO USUÁRIO.

IMPORTANTE: Nem todo áudio é uma reunião comercial B2B! Extraia o máximo de valor de qualquer gravação (pessoal, saúde, jurídico, tech ou negócios).

--- TEMPLATES ADAPTATIVOS DISPONÍVEIS ---

1. "personal_family" (🌿 Vida Pessoal, Família & Diário):
   - Para: Conversas com família, cuidados da casa, desabafos, rotina, compras, saúde, momentos do dia.
   - JSON Output:
     {
       "template_type": "personal_family",
       "meeting_title": "🌿 Título memorável e acolhedor",
       "teaser": "Resumo de 1 linha",
       "tags": ["Pessoal", "Família", "Rotina"],
       "category": "Pessoal",
       "executive_summary": "Narrativa clara e calorosa do momento e contexto.",
       "personal_moments": ["Momento/Diálogo marcante 1"],
       "commitments_and_promises": [
         {"owner": "Você", "action": "Tarefa pessoal ou doméstica", "deadline_or_context": "Prazo/contexto", "urgency": "ALTA/MEDIA/BAIXA"}
       ],
       "key_highlights": ["Frase ou reflexão marcante"]
     }

2. "b2b_sales" (🏢 Comercial, Pipeline & Negócios B2B):
   - Para: Reuniões corporativas, parceiros (Aktie Now, Vonage, Blue3, BCR), clientes enterprise (ZAMP, Britânia), demos.
   - JSON Output:
     {
       "template_type": "b2b_sales",
       "meeting_title": "🏢 [Empresa/Cliente] — [Tema / Objetivo]",
       "teaser": "Resumo executivo de 1 linha",
       "tags": ["Comercial", "Conta", "Zendesk"],
       "category": "Comercial",
       "executive_summary": "Resumo executivo de 3 a 5 parágrafos focado em decisões e rumos estratégicos.",
       "participants": [
         {"name": "Nome", "role": "Papel / Empresa", "participation_type": "active_speaker / mentioned_observer", "key_stance": "Posicionamento"}
       ],
       "commitments_and_promises": [
         {"owner": "Nome", "action": "Ação específica combinada", "deadline_or_context": "Prazo", "urgency": "ALTA/MEDIA/BAIXA"}
       ],
       "accounts_discussed": [
         {"account_name": "Nome da Conta", "current_situation": "Situação", "opportunity_or_risk": "Oportunidade/Risco", "next_step": "Próximo passo"}
       ],
       "strategic_theses": ["Tese ou argumento chave"],
       "follow_up_emails": [
         {"to": "Participantes", "subject": "Assunto do e-mail", "body": "Corpo do e-mail"}
       ],
       "key_highlights": ["Citação relevante do cliente ou parceiro"]
     }

3. "health_clinical" (🩺 Anamnese Clínica & Saúde):
   - Para: Consultas médicas, relatos de saúde, hipóteses clínicas, exames.
   - JSON Output:
     {
       "template_type": "health_clinical",
       "meeting_title": "🩺 Atendimento / Caso Clínico — [Paciente / Tema]",
       "teaser": "Queixa principal e conduta em 1 linha",
       "tags": ["Saúde", "Clínico"],
       "category": "Saúde",
       "executive_summary": "Histórico da queixa, evolução clínica e impressões diagnósticas.",
       "strategic_theses": ["Hipótese Diagnóstica 1", "Exame Solicitado"],
       "commitments_and_promises": [
         {"owner": "Paciente / Médico", "action": "Conduta / Prescrição / Retorno", "deadline_or_context": "Prazo", "urgency": "ALTA"}
       ],
       "key_highlights": ["Sintoma relevante ou alerta clínico"]
     }

4. "legal_hearing" (⚖️ Jurídico, Audiência & Prazos):
   - Para: Audiências, alinhamentos processuais, teses de defesa, acordos.
   - JSON Output:
     {
       "template_type": "legal_hearing",
       "meeting_title": "⚖️ [Processo / Cliente] — [Objeto / Audiência]",
       "teaser": "Síntese processual em 1 linha",
       "tags": ["Jurídico", "Processo"],
       "category": "Jurídico",
       "executive_summary": "Resumo dos fatos alegados, teses debatidas e deliberações do ato.",
       "strategic_theses": ["Tese jurídica aplicada", "Jurisprudência / Artigo de lei"],
       "commitments_and_promises": [
         {"owner": "Advogado / Parte", "action": "Petição / Prazo fatal / Diligência", "deadline_or_context": "Prazo", "urgency": "ALTA"}
       ],
       "key_highlights": ["Acordo formalizado ou decisão do juízo"]
     }

5. "product_tech" (🚀 Tecnologia, Engenharia & Arquitetura):
   - Para: RFCs, discussões técnicas, débitos de engenharia, deploys, sprint, ideias de produto.
   - JSON Output:
     {
       "template_type": "product_tech",
       "meeting_title": "🚀 [Módulo / Sistema] — [Decisão Técnica]",
       "teaser": "Resumo da decisão em 1 linha",
       "tags": ["Engenharia", "Arquitetura", "Tech"],
       "category": "Tecnologia",
       "executive_summary": "Contexto do problema, trade-offs analisados e arquitetura escolhida.",
       "strategic_theses": ["Especificação técnica / ADR", "Débito técnico a pagar"],
       "commitments_and_promises": [
         {"owner": "Engenheiro", "action": "Pull Request / Spike / Migração", "deadline_or_context": "Sprint", "urgency": "ALTA"}
       ],
       "key_highlights": ["Requisito não-funcional ou restrição de sistema"]
     }

6. "consulting_strategy" (💡 Consultoria & Projetos Estratégicos):
   - Para: Diagnósticos, workshops de projetos, roadmap de transformação.
   - JSON Output:
     {
       "template_type": "consulting_strategy",
       "meeting_title": "💡 [Projeto / Cliente] — [Marco Estratégico]",
       "teaser": "Diagnóstico e entrega em 1 linha",
       "tags": ["Consultoria", "Projetos"],
       "category": "Consultoria",
       "executive_summary": "Diagnóstico do estado atual, metodologia proposta e recomendações.",
       "strategic_theses": ["Entregável previsto", "Risco do projeto"],
       "commitments_and_promises": [
         {"owner": "Consultor / Cliente", "action": "Entregável / Validação", "deadline_or_context": "Marco", "urgency": "ALTA"}
       ],
       "key_highlights": ["Insight de negócio ou gargalo identificado"]
     }

7. "general_note" (⚡ Síntese Executiva / Nota Geral / Recado):
   - Para: Notas executivas gerais, pensamentos e áudios curtos.
   - JSON Output:
     {
       "template_type": "general_note",
       "meeting_title": "⚡ [Assunto Principal]",
       "teaser": "Síntese em 1 linha",
       "tags": ["Geral", "Executivo"],
       "category": "Geral",
       "executive_summary": "Síntese executiva direta com contexto, decisões e alinhamentos.",
       "commitments_and_promises": [
         {"owner": "Você", "action": "Ação ou compromisso", "deadline_or_context": "Prazo", "urgency": "ALTA/MEDIA/BAIXA"}
       ],
       "key_highlights": ["Ponto principal ou insight"]
     }
"""

def clean_and_parse_json(raw_text: str) -> Dict[str, Any]:
    """Sanitizes raw LLM output, strips Markdown blocks and parses robustly."""
    if not raw_text or not raw_text.strip():
        return {"error": "Empty response received"}

    cleaned = raw_text.strip()
    
    # Strip markdown ```json ... ``` fences
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\n", "", cleaned)
        cleaned = re.sub(r"\n```$", "", cleaned)
        cleaned = cleaned.strip()

    # Extract JSON object substring
    json_match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
    if json_match:
        cleaned = json_match.group(1)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.warning(f"Initial JSON parse failed: {e}. Attempting recovery sanitization...")
        sanitized = re.sub(r"[\x00-\x1f\x7f-\x9f]", " ", cleaned)
        try:
            return json.loads(sanitized)
        except Exception as final_err:
            logger.error(f"Failed to recover JSON: {final_err}")
            return {"error": f"JSON parsing failed: {str(final_err)}", "raw_response": raw_text}


class IntelligenceEngine:
    """Enterprise AI intelligence engine with acoustic entity normalization, adaptive templates, hierarchical chunking and semantic RAG."""

    def __init__(self, api_key: str = OPENAI_API_KEY, vocab_engine: Optional[AcousticVocabularyEngine] = None):
        self.client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY") or "sk-dummy-startup-key")
        self.learning_engine = SelfLearningEngine(openai_key=api_key)
        self.vocab_engine = vocab_engine or default_vocab_engine

    def generate_embedding(self, text: str) -> List[float]:
        """Generates 1536-dimensional embedding vector for semantic search."""
        if not text or not text.strip():
            return [0.0] * 1536
        try:
            resp = self.client.embeddings.create(
                input=[text.replace("\n", " ")[:8000]],
                model="text-embedding-3-small"
            )
            return resp.data[0].embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return [0.0] * 1536

    def _extract_chunk_summary(self, chunk_text: str, chunk_idx: int, total_chunks: int) -> str:
        """Processes a section of a long transcript during the Map phase."""
        prompt = f"""Analise este bloco {chunk_idx}/{total_chunks} de uma gravação longa.
Extraia em tópicos objetivos:
- Principais decisões e discussões ocorridas neste trecho
- Compromissos, tarefas e donos citados
- Nomes de contas, clientes, parceiros e pessoas mencionados

TRECHO {chunk_idx}/{total_chunks}:
\"\"\"{chunk_text}\"\"\"
"""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.1,
                messages=[
                    {"role": "system", "content": "Você é um extrator analítico de seções de reuniões."},
                    {"role": "user", "content": prompt}
                ]
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"Error processing chunk {chunk_idx}: {e}")
            return f"[Resumo do bloco {chunk_idx} indisponível devido a erro: {e}]"

    def _process_long_transcript_hierarchical(self, clean_transcript: str, chunk_size: int = 12000) -> str:
        """Hierarchical Map-Reduce aggregation for long transcripts (> 1h / > 15k chars)."""
        logger.info(f"Long transcript detected ({len(clean_transcript)} chars). Running hierarchical chunking...")
        chunks = [clean_transcript[i:i + chunk_size] for i in range(0, len(clean_transcript), chunk_size)]
        total = len(chunks)
        
        chunk_summaries = []
        for idx, chunk in enumerate(chunks, 1):
            logger.info(f"Processing chunk {idx}/{total}...")
            c_sum = self._extract_chunk_summary(chunk, idx, total)
            chunk_summaries.append(f"--- SÍNTESE DO BLOCO {idx}/{total} ---\n{c_sum}\n")

        aggregated_notes = "\n".join(chunk_summaries)
        return aggregated_notes

    def analyze(
        self, 
        transcript_text: str, 
        metadata: Optional[Dict[str, Any]] = None, 
        user_id: str = "default_user", 
        target_template: Optional[str] = None, 
        profession: str = "general",
        human_notes: Optional[str] = None, 
        human_weight: float = 1.0,
        model_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyzes transcript using LLM with learned user profile, acoustic normalization, human canvas fusion and multi-template support."""
        logger.info(f"Running intelligence analysis (template={target_template or 'auto'}, profession={profession}, human_weight={human_weight}) for user: {user_id}...")

        # 1. Pre-normalize acoustic STT mishearings deterministically
        clean_transcript = self.vocab_engine.normalize_text(transcript_text)

        # 2. Check if Hierarchical Chunking is needed for very long audio
        is_long = len(clean_transcript) > 40000
        working_transcript = clean_transcript
        if is_long:
            working_transcript = self._process_long_transcript_hierarchical(clean_transcript)

        # 3. Dynamic Model Routing
        chosen_model = model_name or ("gpt-4o-mini" if target_template == "quick_note" or len(clean_transcript) < 800 else "gpt-4o")

        context_info = ""
        if metadata:
            context_info = f"\nMetadados da gravação: {json.dumps(metadata, ensure_ascii=False)}\n"

        profession_spec = PROFESSION_PROMPT_SPECIALIZATIONS.get(profession.lower(), PROFESSION_PROMPT_SPECIALIZATIONS["general"])

        template_directive = ""
        if target_template:
            template_directive = f"\nATENÇÃO: O usuário escolheu OBRIGATORIAMENTE o template '{target_template}'. Estruture o JSON e o tom exatamente de acordo com o template '{target_template}'.\n"
        else:
            template_directive = f"\nESPECIALIZAÇÃO ATIVA:\n{profession_spec}\n\nIdentifique automaticamente o template mais adequado baseado no teor real do áudio e na especialização ativa.\n"

        # 4. Inject learned user profile
        user_context = self.learning_engine.build_prompt_injection(user_id)

        # 5. Inject Acoustic Lexicon Glossary in system prompt
        acoustic_glossary_block = self.vocab_engine.build_prompt_glossary()

        # 6. Inject Human Canvas with authority weight
        human_fusion_block = ""
        if human_notes and human_notes.strip():
            human_fusion_block = f"""
=== ✍️ ANOTAÇÕES HUMANAS AO VIVO (HUMAN CANVAS — PESO DE PRIORIDADE: {human_weight:.1f}x) ===
\"\"\"{human_notes.strip()}\"\"\"
=== FIM DAS ANOTAÇÕES HUMANAS ===

⚠️ DIRETRIZES DE FUSÃO HUMANA (HUMAN-IN-THE-LOOP — PESO MÁXIMO):
1. As notas acima foram registradas pelo próprio usuário ({user_id}) durante/após a reunião.
2. Em qualquer conflito factual entre a transcrição acústica e as notas humanas (ex: valores de negociação, prazos, pessoas envolvidas), AS NOTAS HUMANAS TÊM PRIORIDADE TOTAL.
3. Incorpore ativamente os tópicos e termos das notas humanas no 'executive_summary', 'commitments_and_promises' e nas tarefas geradas.
"""

        transcript_label = "SÍNTESE HIERÁRQUICA DOS BLOCOS DA GRAVAÇÃO" if is_long else "TRANSCRIÇÃO COMPLETA"
        prompt = f"""Analise o conteúdo de áudio e notas humanas, extraindo a inteligência completa no formato JSON especificado.
{template_directive}
{user_context}
{human_fusion_block}

{context_info}
--- {transcript_label} ---
{working_transcript}
--- FIM ---
"""

        system_instruction = f"{MULTI_TEMPLATE_SYSTEM_PROMPT}\n\n{profession_spec}\n\n{acoustic_glossary_block}"

        # 7. LLM Inference with dynamic fallback
        try:
            response = self.client.chat.completions.create(
                model=chosen_model,
                temperature=0.2,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt}
                ]
            )
            raw_json = response.choices[0].message.content or "{}"
        except Exception as primary_err:
            logger.warning(f"Primary model {chosen_model} failed: {primary_err}. Triggering fallback to gpt-4o-mini...")
            try:
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    temperature=0.2,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": system_instruction},
                        {"role": "user", "content": prompt}
                    ]
                )
                raw_json = response.choices[0].message.content or "{}"
            except Exception as fallback_err:
                logger.error(f"Fallback model also failed: {fallback_err}")
                return {"error": f"LLM Inference failed: {str(fallback_err)}"}

        # 8. Robust JSON Parsing & Post-Normalization
        try:
            cleaned_json_str = self.vocab_engine.normalize_text(raw_json)
            structured_data = clean_and_parse_json(cleaned_json_str)
            logger.info(f"Intelligence extraction successful (template={structured_data.get('template_type')}).")

            # 9. Calibrate user profile from this meeting
            try:
                self.learning_engine.calibrate_from_meeting(user_id, clean_transcript, structured_data)
            except Exception as calib_err:
                logger.error(f"Error during self-learning calibration: {calib_err}")

            return structured_data
        except Exception as e:
            logger.error(f"Failed to post-process JSON: {e}")
            return {"error": str(e), "raw_response": raw_json}

    def ask_my_voice_with_citations(self, query: str, retrieved_chunks: list, user_id: str = "default_user") -> Dict[str, Any]:
        """Synthesizes executive cross-meeting answer with precise citations."""
        sources_context = []
        for idx, chunk in enumerate(retrieved_chunks, 1):
            sources_context.append(f"""
--- FONTE [{idx}] ---
ID da Reunião: {chunk.get('file_id') or chunk.get('meeting_id')}
Título: {chunk.get('title') or chunk.get('meeting_title')}
Data / Canal: {chunk.get('start_time', 'Recente')} ({chunk.get('channel', 'Plaud Note')})
Categoria: {chunk.get('category', 'Geral')}
Resumo: {chunk.get('executive_summary', '')[:400]}
Notas Humanas: {chunk.get('human_canvas') or chunk.get('custom_notes', '')[:300]}
Trecho Transcrição:
"{chunk.get('transcript_full', '')[:800]}"
--- FIM FONTE [{idx}] ---
""")

        glossary_block = self.vocab_engine.build_prompt_glossary()

        prompt = f"""Você é o Ask My Voice — o motor de busca semântica e oráculo de voz do EvoNotes para {user_id}.
Sua missão é responder à dúvida do usuário com PRECISÃO CIRÚRGICA e CITAÇÕES AUDITÁVEIS baseadas no histórico de áudios.

DIRETRIZES:
1. Responda em tom analítico, direto e estruturado.
2. Para cada fato, valor, nome de cliente, decisão ou prazo, insira obrigatoriamente a citação no formato [1], [2] referenciando as fontes numeradas.
3. Se houver compromissos ou tarefas relacionadas, liste-os claramente.

{glossary_block}

FONTES DE ÁUDIO RECUPERADAS:
{"".join(sources_context)}

PERGUNTA DO USUÁRIO:
{query}

Retorne um JSON estrito no formato:
{{
  "answer_markdown": "Texto da resposta estruturada com formatação markdown e citações [1], [2]...",
  "direct_answer": "Resumo de 1 frase para leitura rápida",
  "citations": [
    {{
      "citation_number": 1,
      "meeting_id": "ID",
      "meeting_title": "Título da Reunião",
      "date": "Data",
      "channel": "Canal",
      "quote_snippet": "Frase ou contexto relevante"
    }}
  ],
  "commitments_found": ["Compromisso 1", "Compromisso 2"]
}}
"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                temperature=0.1,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": "Você é o Oráculo Semântico Ask My Voice."},
                    {"role": "user", "content": prompt}
                ]
            )
            raw_text = response.choices[0].message.content or "{}"
            return clean_and_parse_json(raw_text)
        except Exception as e:
            logger.error(f"Error in ask_my_voice_with_citations: {e}")
            return {"error": str(e), "direct_answer": "Erro ao consultar histórico de voz.", "citations": []}


def normalize_text_vocabulary(text: str) -> str:
    return default_vocab_engine.normalize_text(text)

if __name__ == "__main__":
    engine = IntelligenceEngine()
    print("EvoNotes IntelligenceEngine v2 with 5 Pillars ready.")
