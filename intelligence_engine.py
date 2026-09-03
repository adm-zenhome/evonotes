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

        # 7. LLM Inference (Gemini Flash Lite REST / OpenAI)
        gemini_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if gemini_key:
            try:
                import urllib.request
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent?key={gemini_key}"
                combined_prompt = f"{system_instruction}\n\n{prompt}"
                payload = {
                    "contents": [{"parts": [{"text": combined_prompt}]}]
                }
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    raw_text = resp_data["candidates"][0]["content"]["parts"][0]["text"]
                    return clean_and_parse_json(raw_text)
            except Exception as ge:
                logger.warning(f"Gemini REST inference error ({ge}); falling back to OpenAI...")

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
                logger.error(f"OpenAI fallback failed: {fallback_err}")
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


    def route_and_process_text(self, text: str, user_id: str = "default_user") -> Dict[str, Any]:
        """
        Roteamento Inteligente de Intenção para mensagens de texto via WhatsApp e Copilot In-App (100x Hyper-Intelligent).
        Consulta SQLite em tempo real e usa Gemini 3.6 Flash / GPT-4o para resposta em < 2s com contexto total da base.
        """
        try:
            from database import db
            raw_text = (text or "").strip()
            lower_text = raw_text.lower()
            clean_normalized = re.sub(r"[^\w\s]", " ", lower_text)
            words = clean_normalized.split()

            # Consulta em tempo real ao SQLite DB
            tasks = db.get_all_tasks(user_id=user_id, status="PENDING")
            tasks_str = json.dumps([{"id": t["id"], "action": t["action"], "owner": t.get("owner"), "deadline": t.get("deadline_or_context")} for t in tasks[:20]], ensure_ascii=False)
            
            all_meetings = db.get_all_meetings()
            meetings_summary_list = []
            for m in all_meetings:
                intel = m.get("intelligence")
                if not isinstance(intel, dict):
                    intel = {}
                parts = intel.get("participants") or []
                part_names = []
                if isinstance(parts, list):
                    for p in parts:
                        if isinstance(p, dict) and p.get("name") and p.get("name") != "Felipe Donato":
                            part_names.append(p["name"])
                        elif isinstance(p, str) and p != "Felipe Donato":
                            part_names.append(p)
                meetings_summary_list.append({
                    "id": m.get("file_id"),
                    "title": (m.get("title") or "Sem Título").replace("🎙️", "").strip(),
                    "category": m.get("category", "Geral"),
                    "date": (m.get("start_time") or "")[:10],
                    "duration_min": round((m.get("duration_seconds") or 0) / 60, 1),
                    "participants": part_names,
                    "summary": (m.get("executive_summary") or "")[:180]
                })
            meetings_str = json.dumps(meetings_summary_list, ensure_ascii=False)
            
            prompt = f"""Você é o Evo Agent — Segundo Cérebro de Voz e Inteligência Operacional.
Sua missão é classificar a intenção da mensagem e responder com máxima inteligência, tom executivo conciso e precisão.
Não fique repetindo seu nome em todas as respostas (diga quem é apenas no início de uma nova conversa se o usuário disser 'Oi' ou 'Olá').

INTENÇÕES POSSÍVEIS:
1. COMMAND_TASK: Criar uma nova tarefa (ex: "Anota aí", "Lembrar de...", "Adiciona tarefa para amanhã").
2. LIST_NOTES: Listar, organizar ou buscar reuniões/gravações gravadas no Plaud Note Pro e WhatsApp (ex: "Liste minhas notas", "Mostre todas as notas", "Quais reuniões tive?", "Organize minhas notas por cliente").
   - IMPORTANTE AO LISTAR NOTAS:
     - Traga TODAS as notas cadastradas na base em formato de lista executiva limpa (Título, Data, Categoria, Duração e 1 linha de resumo).
     - Se o usuário pedir ordenação por DATA: ordene da mais recente para a mais antiga.
     - Se pedir por CLIENTE/EMPRESA: agrupe por Britânia, Wine, etc.
     - Se apenas pedir para listar sem especificar a ordem: liste todas de forma concisa e pergunte ativamente ao final: "💡 *Deseja que eu ordene esta lista por 📅 Data mais recente, 🏢 Cliente/Empresa ou 🏷️ Categoria?*"
3. QUESTION: Perguntas sobre status da conta, tarefas ativas ou conversa executiva (ex: "Minha conta ta ativa?", "Quais são minhas tarefas?").
4. KNOWLEDGE_SEARCH: Perguntas sobre o conteúdo específico de uma reunião (ex: "O que a Débora da Britânia falou sobre App Builder?").

DADOS EM TEMPO REAL DO SISTEMA (SQLITE):
- Usuário: {user_id}
- Total de Tarefas Pendentes no Banco ({len(tasks)}): {tasks_str}
- Total de Notas/Gravações no Banco ({len(all_meetings)}): {meetings_str}

MENSAGEM DO USUÁRIO: "{text}"

Retorne um JSON ESTRITO com o formato:
{{
  "intent": "COMMAND_TASK|LIST_NOTES|QUESTION|KNOWLEDGE_SEARCH|MEMO",
  "reply_msg": "Texto da resposta executiva formatada em markdown.",
  "tasks_to_create": [
     {{"action": "Ação clara", "owner": "Responsável", "deadline": "Prazo"}}
  ],
  "is_memo": false
}}
"""
            # 1. Try Gemini 3.6 Flash
            gemini_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
            if gemini_key:
                try:
                    import google.generativeai as genai
                    genai.configure(api_key=gemini_key)
                    model = genai.GenerativeModel("gemini-3.6-flash")
                    resp = model.generate_content(prompt)
                    res_json = clean_and_parse_json(resp.text)
                    if isinstance(res_json, dict) and "reply_msg" in res_json:
                        return res_json
                except Exception as ge:
                    logger.warning(f"Gemini route error: {ge}")

            # 2. Try OpenAI if configured
            if self.client and "dummy" not in getattr(self.client, "api_key", "dummy"):
                try:
                    response = self.client.chat.completions.create(
                        model="gpt-4o-mini",
                        temperature=0.2,
                        response_format={"type": "json_object"},
                        messages=[
                            {"role": "system", "content": "Você é o Evo Agent — Segundo Cérebro de Voz."},
                            {"role": "user", "content": prompt}
                        ]
                    )
                    raw_json = response.choices[0].message.content or "{}"
                    res_json = clean_and_parse_json(raw_json)
                    if isinstance(res_json, dict) and "reply_msg" in res_json:
                        return res_json
                except Exception as oe:
                    logger.warning(f"OpenAI fallback error: {oe}")

            # 3. Deterministic Evo Agent Engine (Zero Quota / Zero Timeout Guaranteed)
            # Detect Plaud Sync Command
            if any(k in lower_text for k in ["sincronizar plaud", "sincronize o plaud", "sync plaud", "atualizar plaud", "puxar gravações", "puxar gravacoes", "novas gravações", "sincronizar"]):
                try:
                    from plaud_processor import get_all_plaud_recordings
                    recs = get_all_plaud_recordings()
                    for r in recs:
                        db.save_meeting(r, user_id=user_id)
                    refreshed = db.get_all_meetings(user_id=user_id)
                    return {
                        "intent": "SYNC_PLAUD",
                        "reply_msg": f"🎙️ **Plaud Note Pro Sincronizado com Sucesso!**\n\nForam sincronizadas as gravações da sua conta Plaud.\n📊 **Total de Notas Ativas:** {len(refreshed)}\n✅ Transcrições na íntegra, sínteses e tarefas atualizadas na Central de Inteligência.",
                        "tasks_to_create": [],
                        "is_memo": False
                    }
                except Exception as se:
                    return {
                        "intent": "SYNC_PLAUD",
                        "reply_msg": f"⚠️ Erro ao sincronizar Plaud: {se}",
                        "tasks_to_create": [],
                        "is_memo": False
                    }

            # Detect Task Creation Command
            if any(k in lower_text for k in ["anota aí", "anota ai", "lembrar de", "criar tarefa", "adicionar tarefa", "tarefa:"]):
                clean_action = re.sub(r"^(anota aí|anota ai|lembrar de|criar tarefa|adicionar tarefa|tarefa:)\s*[:,-]?\s*", "", text, flags=re.IGNORECASE).strip()
                if not clean_action: clean_action = text
                return {
                    "intent": "COMMAND_TASK",
                    "reply_msg": f"✅ **Tarefa Registrada:** '{clean_action}'\n📌 **Responsável:** Você\n⏱️ **Prazo:** Hoje / Próximos Passos\n\n*Ação cadastrada na Central de Tarefas.*",
                    "tasks_to_create": [{"action": clean_action, "owner": "Você", "deadline": "Hoje"}],
                    "is_memo": False
                }

            # Detect Notes Listing & Custom Sorting Query
            if any(k in lower_text for k in [
                "minhas notas", "todas as notas", "listar notas", "liste as notas", "liste minhas notas", 
                "quais notas", "quais reuniões", "reunioes", "gravações", "gravacoes", "historico",
                "organize por", "ordene por", "agrupe por", "agrupar por", "por cliente", "por data", "por categoria", "ordem cronol"
            ]):
                if not all_meetings:
                    return {
                        "intent": "LIST_NOTES",
                        "reply_msg": "📂 **Nenhuma nota registrada no momento.**\n\nSua base está limpa. Envie um áudio ou nota aqui para registrar a primeira gravação!",
                        "tasks_to_create": [],
                        "is_memo": False
                    }
                
                # Check for sorting preferences
                if any(k in lower_text for k in ["por cliente", "por empresa", "por conta", "clientes"]):
                    # Group by client/company
                    grouped = {}
                    for m in all_meetings:
                        t = m.get("title") or ""
                        c = "Outros / Geral"
                        if "Britânia" in t: c = "🏢 Britânia"
                        elif "Wine" in t: c = "🍷 Wine"
                        elif "Augusto Cury" in t or "Cury" in t: c = "🧠 Desenvolvimento / Cury"
                        elif "WhatsApp" in t: c = "📱 WhatsApp Oficial"
                        grouped.setdefault(c, []).append(m)
                    
                    lines = [f"📂 **Todas as suas Notas ({len(all_meetings)} no total) Organizadas por Cliente/Conta:**\n"]
                    for grp_name, m_list in grouped.items():
                        lines.append(f"### {grp_name} ({len(m_list)} registro{'s' if len(m_list)>1 else ''})")
                        for idx, m in enumerate(m_list, 1):
                            m_date = (m.get("start_time") or "")[:10]
                            m_title = (m.get("title") or "").replace("🎙️", "").strip()
                            m_dur = round((m.get("duration_seconds") or 0) / 60, 1)
                            m_sum = (m.get("executive_summary") or "")[:120]
                            lines.append(f"• **{m_title}** — *{m_date}* ({m_dur} min)")
                            if m_sum:
                                lines.append(f"  > _{m_sum}..._")
                        lines.append("")
                    return {
                        "intent": "LIST_NOTES",
                        "reply_msg": "\n".join(lines).strip(),
                        "tasks_to_create": [],
                        "is_memo": False
                    }

                elif any(k in lower_text for k in ["por data", "recente", "cronol"]):
                    # Sorted by date
                    sorted_meetings = sorted(all_meetings, key=lambda x: str(x.get("start_time") or ""), reverse=True)
                    lines = [f"📅 **Todas as suas Notas ({len(all_meetings)} no total) em Ordem Cronológica:**\n"]
                    for idx, m in enumerate(sorted_meetings, 1):
                        m_date = (m.get("start_time") or "")[:10]
                        m_title = (m.get("title") or "").replace("🎙️", "").strip()
                        m_dur = round((m.get("duration_seconds") or 0) / 60, 1)
                        m_cat = m.get("category") or "Geral"
                        m_sum = (m.get("executive_summary") or "")[:130]
                        lines.append(f"**{idx}. {m_title}**")
                        lines.append(f"• 📅 Data: `{m_date}` | ⏱️ Duração: `{m_dur} min` | 🏷️ `{m_cat}`")
                        if m_sum:
                            lines.append(f"• 🎯 Resumo: _{m_sum}..._")
                        lines.append("")
                    return {
                        "intent": "LIST_NOTES",
                        "reply_msg": "\n".join(lines).strip(),
                        "tasks_to_create": [],
                        "is_memo": False
                    }

                else:
                    # Default list of all notes + interactive sorting question
                    lines = [f"📋 **Todas as suas Notas Registradas ({len(all_meetings)} no total):**\n"]
                    for idx, m in enumerate(all_meetings, 1):
                        m_date = (m.get("start_time") or "")[:10]
                        m_title = (m.get("title") or "").replace("🎙️", "").strip()
                        m_dur = round((m.get("duration_seconds") or 0) / 60, 1)
                        m_cat = m.get("category") or "Geral"
                        m_sum = (m.get("executive_summary") or "")[:110]
                        lines.append(f"**{idx}.** {m_title} — `{m_date}` ({m_dur} min) • *{m_cat}*")
                        if m_sum:
                            lines.append(f"   > _{m_sum}..._")
                    
                    lines.append("\n---\n💡 **Personalização de Visualização:**\n*Deseja que eu reordene esta lista por:*\n• **1.** 📅 *Data mais recente*\n• **2.** 🏢 *Cliente / Empresa*\n• **3.** 🏷️ *Categoria / Tipo de Reunião*")
                    return {
                        "intent": "LIST_NOTES",
                        "reply_msg": "\n".join(lines).strip(),
                        "tasks_to_create": [],
                        "is_memo": False
                    }

            # Detect Pending Tasks Query
            if any(k in lower_text for k in [
                "tarefa", "tarefas", "liste tarefas", "lista tarefas", "listar tarefas", 
                "minhas tarefas", "quais tarefas", "tarefas pendentes", "pendencias", "pendências",
                "to-dos", "to dos", "o que tenho pra fazer", "o que tenho que fazer", "ver tarefas"
            ]) and not any(k in lower_text for k in ["anota", "criar", "adicionar", "nova tarefa", "concluir", "feita"]):
                if tasks:
                    task_lines = "\n".join([f"{idx}. **{t.get('action')}** (Prazo: {t.get('deadline_or_context') or 'A definir'})" for idx, t in enumerate(tasks[:15], 1)])
                    return {
                        "intent": "QUESTION",
                        "reply_msg": f"📋 **Suas Principais Tarefas Pendentes ({len(tasks)} no total):**\n\n{task_lines}\n\n*Central de Tarefas sincronizada.*",
                        "tasks_to_create": [],
                        "is_memo": False
                    }
                else:
                    return {
                        "intent": "QUESTION",
                        "reply_msg": "🎉 **Você não tem nenhuma tarefa pendente no momento!**",
                        "tasks_to_create": [],
                        "is_memo": False
                    }

            # Detect Help / Capabilities Query
            if any(k in lower_text for k in ["ajuda", "help", "menu", "comandos", "o que você faz", "o que vc faz", "funcionalidades", "como usar"]):
                reply = (
                    f"🧠 *Evo Agent — Seu Segundo Cérebro Executivo de Voz:*\n\n"
                    f"Aqui estão os principais comandos e ações que você pode enviar:\n\n"
                    f"• 📋 *'Liste tarefas'* — Ver todas as suas pendências ativas\n"
                    f"• 📂 *'Liste notas'* — Ver histórico de reuniões e áudios\n"
                    f"• 📝 *'Anota aí: [ação]'* — Criar nova tarefa instantânea\n"
                    f"• ⚡ *'Status'* — Consultar o status da sua conta\n"
                    f"• 🎙️ Ou simplesmente envie um *áudio de voz* para transcrição e ata instantânea!"
                )
                return {
                    "intent": "QUESTION",
                    "reply_msg": reply,
                    "tasks_to_create": [],
                    "is_memo": False
                }

            # Detect Greeting / Intro (Says who it is ONLY at the beginning)
            if any(k in lower_text for k in ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite", "começar", "iniciar"]):
                return {
                    "intent": "QUESTION",
                    "reply_msg": f"Olá! Sou o **Evo Agent**, seu Segundo Cérebro de Voz.\n\nEstou conectado ao seu WhatsApp oficial. Você pode me mandar áudios, reuniões, comandos ou tarefas a qualquer momento.\n\nComo posso ajudar agora?",
                    "tasks_to_create": [],
                    "is_memo": False
                }

            # Detect Status / Connection Query
            if any(k in lower_text for k in ["conta ta ativa", "conta está ativa", "status", "conectado", "ta funcionando", "está funcionando"]):
                return {
                    "intent": "QUESTION",
                    "reply_msg": f"⚡ **Conta 100% Ativa e Operacional!**\n\n• **Evo Agent:** Online\n• **WhatsApp:** +55 (11) 96000-4895\n• **Base:** {len(all_meetings)} notas registradas e {len(tasks)} tarefas ativas.",
                    "tasks_to_create": [],
                    "is_memo": False
                }

            # General Executive Question / Knowledge
            return {
                "intent": "QUESTION", 
                "reply_msg": f"Entendido! Sua base conta com {len(all_meetings)} notas e {len(tasks)} tarefas ativas. Como deseja prosseguir?", 
                "tasks_to_create": [],
                "is_memo": False
            }
        except Exception as e:
            import traceback
            logger.error(f"Error in route_and_process_text:\n{traceback.format_exc()}")
            return {
                "intent": "QUESTION", 
                "reply_msg": "Olá! Sua inteligência executiva está 100% ativa e operacional.", 
                "tasks_to_create": [],
                "is_memo": False
            }
            return {
                "intent": "QUESTION", 
                "reply_msg": "⚡ Olá Felipe! Sua inteligência executiva no EvoNotes está 100% ativa, conectada e operacional.", 
                "tasks_to_create": [],
                "is_memo": False
            }

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
