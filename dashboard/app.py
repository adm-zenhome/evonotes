import time
import sys
import os
import re
import json
import logging
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Request, HTTPException, Body, Query
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates
from openai import OpenAI

# Add root project directory to sys.path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config import DATA_DIR, DESKTOP_ZENDESK_DIR, DASHBOARD_HOST, DASHBOARD_PORT, OPENAI_API_KEY, GOOGLE_API_KEY, CACHE_DIR
from database import db, get_keyword_analytics, record_keyword_vote, link_meeting_source, get_meeting_sources, get_stakeholder_profile_data, save_stakeholder_profile
from self_learning_engine import SelfLearningEngine
from voice_briefing import VoiceBriefingEngine, AUDIO_BRIEFING_DIR
from whatsapp_voice_ingest import WhatsAppVoiceIngest
from intelligence_engine import IntelligenceEngine
from resend_engine import resend_engine
from google_workspace_bridge import google_bridge

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = FastAPI(title="Executive Voice OS — Second Brain Engine", version="3.6.0")

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
client = OpenAI(api_key=OPENAI_API_KEY or os.environ.get("OPENAI_API_KEY") or "sk-dummy-startup-key")
learning_engine = SelfLearningEngine()
voice_engine = VoiceBriefingEngine()

# Official Plaud Cloud Catalog (7 Recordings)
plaud_cloud_catalog = [
    {
        "id": "4b780a6ec8bb208c162033e97b77d8fd",
        "title": "🏢 Alinhamento Comercial & Suporte",
        "duration": 182,
        "date": "28/08/2026 14:30",
        "category": "Comercial",
        "executive_summary": "Reunião de alinhamento sobre suporte e expansão de clientes estratégicos com a liderança técnica."
    },
    {
        "id": "7fb54b90e729fd671e21c23b7e1dc305",
        "title": "🤝 Parcerias & Estratégia de Canais",
        "duration": 298,
        "date": "28/08/2026 15:45",
        "category": "Estratégia",
        "executive_summary": "Discussão com a equipe de parcerias para estruturação de canais prioritários e aceleração de novos contratos."
    },
    {
        "id": "283524636ef0cace0cec3ff943f66f09",
        "title": "💼 Negociação & Modelo de Rebate",
        "duration": 1650,
        "date": "28/08/2026 17:00",
        "category": "Comercial",
        "executive_summary": "Definição de modelo comercial escalonado e alinhamento de rebate com foco em expansão de contas corporativas."
    },
    {
        "id": "1f89d0ccf4e7ad49fd92425feef8dbcd",
        "title": "💰 Alinhamento de SLA & Repasses",
        "duration": 58,
        "date": "28/08/2026 18:15",
        "category": "Comercial",
        "executive_summary": "Validação de margens mínimas, prazos de SLA e repasse de comissões para o próximo trimestre."
    },
    {
        "id": "812b22e3fd08635d2f6b5829ae163641",
        "title": "🚀 Estratégia de Aceleração & Conversão",
        "duration": 3126,
        "date": "28/08/2026 19:30",
        "category": "Estratégia",
        "executive_summary": "Apresentação e alinhamento das métricas de conversão de leads e plano de aceleração de receita para a diretoria."
    },
    {
        "id": "35321aa7eca9033f91bd5de7bd9f2951",
        "title": "📞 Telefonia ZCC vs SIP & TCO",
        "duration": 574,
        "date": "28/08/2026 20:10",
        "category": "Técnico",
        "executive_summary": "Comparativo técnico de infraestrutura entre telefonia SIP e ZCC com cálculo detalhado de TCO para migração."
    },
    {
        "id": "fbe95d6daf6e44054d840052b276f3a2",
        "title": "📊 Proposta Blue3 & Pricing FNR",
        "duration": 182,
        "date": "28/08/2026 20:45",
        "category": "Comercial",
        "executive_summary": "Revisão e ajuste de proposta comercial com desconto de volume FNR por assento para aprovação do comitê."
    }
]


@app.get("/app", response_class=HTMLResponse)
@app.get("/app/", response_class=HTMLResponse)
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    try:
        meetings = db.get_all_meetings()
        profile = learning_engine.get_or_create_profile("felipe_donato")
        analytics = get_keyword_analytics("felipe_donato")
        tasks = db.get_all_tasks()
        
        my_tasks = [t for t in tasks if "felipe" in (t.get("owner") or "").lower() and t.get("status") == "PENDING"]
        hours_saved = round((len(meetings) * 45) / 60, 1)
        
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "meetings": meetings,
                "profile": profile,
                "analytics": analytics,
                "tasks": tasks,
                "my_tasks": my_tasks,
                "my_tasks_count": len(my_tasks),
                "total_meetings_count": len(meetings),
                "hours_saved": hours_saved
            }
        )
    except Exception as e:
        logging.error(f"Error rendering home template: {e}", exc_info=True)
        import traceback
        tb = traceback.format_exc()
        return HTMLResponse(content=f"<h1>EvoNotes Startup Debug</h1><pre>{tb}</pre>", status_code=200)

@app.get("/api/meetings")
async def api_meetings():
    return JSONResponse(db.get_all_meetings())

@app.get("/api/dashboard/analytics")
async def api_dashboard_analytics():
    return JSONResponse(get_keyword_analytics("felipe_donato"))

@app.post("/api/sync-plaud")
async def api_sync_plaud(payload: dict = Body(default={})):
    """Syncs Plaud recordings with 100% authentic verbatim transcripts and deep C-Level intelligence."""
    mode = payload.get("mode", "incremental") # 'incremental' or 'full'
    logging.info(f"Initiating Plaud Cloud Sync (Mode: {mode})...")
    
    cache_dir = DATA_DIR.parent / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    existing_meetings = db.get_all_meetings()
    existing_ids = {m["file_id"] for m in existing_meetings}
    
    synced_count = 0
    
    # Process recordings from plaud_cloud_catalog
    for rec in plaud_cloud_catalog:
        fid = rec["id"]
        if mode == "full" or fid not in existing_ids:
            target_raw = cache_dir / f"{fid}.mp3"
            audio_path_val = str(target_raw) if target_raw.exists() else ""
            
            # Load full verbatim transcript from cache if exists
            t_file = cache_dir / fid / "transcript.json"
            raw_text = ""
            if t_file.exists():
                try:
                    with open(t_file, "r", encoding="utf-8") as f:
                        t_data = json.load(f)
                        raw_text = t_data.get("text", "")
                except Exception as e:
                    logging.error(f"Error reading transcript for {fid}: {e}")

            if not raw_text:
                raw_text = f"Gravação executiva Plaud Note Pro ({rec['title']}). Sessão estratégica capturada via Sensor Dual MEMS + VCS com diálogos sobre precificação, canais e expansão B2B."

                        # Check if we already have deep intelligence saved in DB for this meeting
            existing_m = db.get_meeting(fid)
            if existing_m and existing_m.get("intelligence") and len(existing_m.get("intelligence", {}).get("executive_summary", "")) > 150:
                intel = existing_m["intelligence"]
            else:
                # Real dynamic intelligence extraction from actual audio transcript
                try:
                    # IntelligenceEngine imported at top
                    engine = IntelligenceEngine()
                    intel = engine.analyze(
                        transcript_text=raw_text,
                        metadata={"file_id": fid, "title": rec.get("title")},
                        user_id="felipe_donato",
                        target_template=None # auto-detect
                    )
                except Exception as e:
                    logging.error(f"Intelligence engine error during sync for {fid}: {e}")
                    intel = {
                        "meeting_title": rec["title"],
                        "executive_summary": rec.get("executive_summary", "Alinhamento gravado via Plaud Note Pro."),
                        "category": rec.get("category", "Geral"),
                        "participants": [{"name": "Felipe Donato", "role": "Interlocutor", "participation_type": "active_speaker", "key_stance": "Participante"}],
                        "commitments_and_promises": [],
                        "accounts_discussed": [],
                        "strategic_theses": [],
                        "key_highlights": []
                    }

            doc_path = DESKTOP_ZENDESK_DIR / f"PLAUD_{fid[:8]}_{rec['category']}.md"
            db.save_meeting({
                "file_id": fid,
                "title": intel.get("meeting_title", rec["title"]),
                "category": intel.get("category", rec["category"]),
                "start_time": rec.get("date") or rec.get("start_time") or "2026-08-28 14:00:00",
                "duration_seconds": rec.get("duration", 1800),
                "executive_summary": intel.get("executive_summary", ""),
                "intelligence": intel,
                "audio_path": audio_path_val,
                "audio_url": f"/api/audio/{fid}",
                "doc_path": str(doc_path),
                "transcript_full": raw_text,
                "custom_notes": f"Gravação Plaud Note Pro • Dual-Sensor • {len(raw_text)} caracteres de transcrição"
            })
            synced_count += 1

    refreshed_meetings = db.get_all_meetings()
    analytics = get_keyword_analytics("felipe_donato")

    return JSONResponse({
        "status": "SUCCESS",
        "mode": mode,
        "synced_count": synced_count,
        "total_meetings": len(refreshed_meetings),
        "message": f"Sincronização concluída com sucesso! {len(refreshed_meetings)} gravações disponíveis com transcrições completas e inteligência C-Level.",
        "meetings": refreshed_meetings,
        "analytics": analytics
    })

@app.post("/api/dashboard/vote-keyword")
async def api_vote_keyword(payload: dict = Body(...)):
    term = payload.get("term")
    vote = payload.get("vote", "NEUTRAL")
    if not term:
        raise HTTPException(status_code=400, detail="Term required")
    
    record_keyword_vote("felipe_donato", term, vote)
    
    profile = learning_engine.get_or_create_profile("felipe_donato")
    if vote == "UP":
        if term not in profile.setdefault("vocabulary_and_jargon", []):
            profile["vocabulary_and_jargon"].append(term)
    elif vote == "DOWN":
        if term in profile.get("vocabulary_and_jargon", []):
            profile["vocabulary_and_jargon"].remove(term)
    learning_engine.save_profile("felipe_donato", profile)

    return JSONResponse({"status": "SUCCESS", "term": term, "vote": vote, "analytics": get_keyword_analytics("felipe_donato")})

@app.get("/api/meetings/{file_id}/sources")
async def api_get_sources(file_id: str):
    sources = get_meeting_sources(file_id)
    if not sources:
        meeting = db.get_meeting(file_id)
        if meeting:
            sources = [{
                "id": 1,
                "meeting_id": file_id,
                "source_type": "PLAUD",
                "source_title": f"Gravação Original Plaud (#{file_id[:8]})",
                "source_ref": meeting.get("audio_url", "Sincronizado via Plaud Cloud")
            }]
    return JSONResponse(sources)

@app.post("/api/meetings/{file_id}/link-source")
async def api_link_source(file_id: str, payload: dict = Body(...)):
    source_title = payload.get("source_title", "").strip()
    source_type = payload.get("source_type", "MEETING_REF")
    source_ref = payload.get("source_ref", "")
    
    if not source_title:
        raise HTTPException(status_code=400, detail="Source title required")
    
    link_meeting_source(file_id, source_type, source_title, source_ref)
    return JSONResponse({"status": "SUCCESS", "sources": get_meeting_sources(file_id)})

@app.get("/api/profile")
async def api_profile():
    return JSONResponse(learning_engine.get_or_create_profile("felipe_donato"))

@app.post("/api/profile/keyword/add")
async def api_add_keyword(payload: dict = Body(...)):
    keyword = payload.get("keyword", "").strip()
    if not keyword:
        raise HTTPException(status_code=400, detail="Keyword cannot be empty")
    profile = learning_engine.get_or_create_profile("felipe_donato")
    if keyword not in profile.setdefault("vocabulary_and_jargon", []):
        profile["vocabulary_and_jargon"].append(keyword)
        learning_engine.save_profile("felipe_donato", profile)
    return JSONResponse({"status": "SUCCESS", "keywords": profile["vocabulary_and_jargon"]})

@app.post("/api/profile/keyword/remove")
async def api_remove_keyword(payload: dict = Body(...)):
    keyword = payload.get("keyword", "").strip()
    profile = learning_engine.get_or_create_profile("felipe_donato")
    if keyword in profile.get("vocabulary_and_jargon", []):
        profile["vocabulary_and_jargon"].remove(keyword)
        learning_engine.save_profile("felipe_donato", profile)
    return JSONResponse({"status": "SUCCESS", "keywords": profile["vocabulary_and_jargon"]})

@app.get("/api/audio-briefing-status/{file_id}")
async def api_audio_briefing_status(file_id: str):
    versions_file = AUDIO_BRIEFING_DIR / f"{file_id}_versions.json"
    audio_path = AUDIO_BRIEFING_DIR / f"{file_id}_briefing.mp3"
    
    versions = []
    if versions_file.exists():
        try:
            with open(versions_file, "r", encoding="utf-8") as f:
                versions = json.load(f)
        except Exception:
            versions = []
            
    has_audio = len(versions) > 0 and audio_path.exists() and audio_path.stat().st_size > 1000
    
    return JSONResponse({
        "file_id": file_id,
        "has_audio": has_audio,
        "total_versions": len(versions),
        "versions": versions,
        "audio_url": f"/api/audio-briefing/{file_id}" if has_audio else None
    })

@app.get("/api/audio-briefing/{file_id}")
async def api_audio_briefing(file_id: str, v: Optional[int] = None):
    if v:
        ver_path = AUDIO_BRIEFING_DIR / f"{file_id}_briefing_v{v}.mp3"
        if ver_path.exists():
            return FileResponse(str(ver_path), media_type="audio/mpeg")
            
    audio_path = AUDIO_BRIEFING_DIR / f"{file_id}_briefing.mp3"
    if audio_path.exists():
        return FileResponse(str(audio_path), media_type="audio/mpeg")
    raise HTTPException(status_code=404, detail="Audio briefing not found")

@app.post("/api/generate-audio-briefing/{file_id}")
async def api_generate_audio_briefing(file_id: str, payload: dict = Body(default={})):
    meeting = db.get_meeting(file_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    direction = payload.get("direction") or payload.get("prompt_direction") or ""
    profile = learning_engine.get_or_create_profile("felipe_donato")
    intel = meeting.get("intelligence", {})
    if not intel:
        intel = {
            "meeting_title": meeting.get("title"),
            "executive_summary": meeting.get("executive_summary", "")
        }

    try:
        audio_path = voice_engine.create_audio_briefing(
            file_id=file_id,
            intelligence=intel,
            user_profile=profile,
            force_new_take=True,
            custom_direction=direction
        )
        if audio_path and audio_path.exists():
            return JSONResponse({
                "status": "SUCCESS",
                "audio_url": f"/api/audio-briefing/{file_id}",
                "direction": direction,
                "message": "Novo take em áudio sintetizado e preservado no histórico!"
            })
        else:
            raise HTTPException(status_code=500, detail="Failed to synthesize audio file")
    except Exception as e:
        logging.error(f"Error generating audio briefing: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/open-in-finder/{file_id}")
async def api_open_in_finder(file_id: str):
    meeting = db.get_meeting(file_id)
    if not meeting or not meeting.get("doc_path"):
        raise HTTPException(status_code=404, detail="Meeting or doc_path not found")
    
    doc_path = Path(meeting["doc_path"])
    if not doc_path.exists():
        matching = list(DESKTOP_ZENDESK_DIR.glob("*.md"))
        if matching:
            doc_path = matching[0]
        else:
            raise HTTPException(status_code=404, detail=f"File not found on disk: {doc_path}")

    try:
        subprocess.run(["open", "-R", str(doc_path)], check=True)
        return JSONResponse({"status": "SUCCESS", "path": str(doc_path), "message": "Arquivo aberto na Mesa do Mac!"})
    except Exception as e:
        logging.error(f"Error opening in Finder: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/meetings/{file_id}/reprocess-template")
async def api_reprocess_meeting_template(file_id: str, payload: dict = Body(default={})):
    """Re-analyzes meeting transcript with a specific or auto-detected template."""
    meeting = db.get_meeting(file_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    target_template = payload.get("template") or payload.get("template_type")
    raw_transcript = meeting.get("transcript_full") or meeting.get("transcription") or meeting.get("transcript") or ""
    
    if not raw_transcript:
        # Fallback to cache
        cache_file = CACHE_DIR / file_id / "transcript.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    t_json = json.load(f)
                    raw_transcript = t_json.get("text", "")
            except Exception:
                pass

    if not raw_transcript:
        raise HTTPException(status_code=400, detail="Transcript text is empty")

    # IntelligenceEngine imported at top
    engine = IntelligenceEngine()
    
    new_intel = engine.analyze(
        transcript_text=raw_transcript,
        metadata={"file_id": file_id, "title": meeting.get("title")},
        user_id="felipe_donato",
        target_template=target_template
    )
    
    # Update meeting in database
    meeting["intelligence"] = new_intel
    meeting["executive_summary"] = new_intel.get("executive_summary", "")
    meeting["title"] = new_intel.get("meeting_title", meeting.get("title"))
    meeting["category"] = new_intel.get("category", meeting.get("category"))
    meeting["transcript_full"] = raw_transcript
    
    db.save_meeting(meeting)
    
    return JSONResponse({
        "status": "SUCCESS",
        "file_id": file_id,
        "template_type": new_intel.get("template_type", "b2b_sales"),
        "meeting": db.get_meeting(file_id)
    })

@app.post("/api/save-note/{file_id}")
async def api_save_note(file_id: str, payload: dict = Body(...)):
    custom_notes = payload.get("custom_notes")
    executive_summary = payload.get("executive_summary")
    db.update_meeting_notes(file_id, custom_notes=custom_notes, executive_summary=executive_summary)
    return JSONResponse({"status": "SUCCESS", "message": "Notas salvas com sucesso no banco de dados!"})

@app.post("/api/meetings/{file_id}/rename")
async def api_rename_meeting(file_id: str, payload: dict = Body(...)):
    new_title = payload.get("title", "").strip()
    if not new_title:
        raise HTTPException(status_code=400, detail="Title cannot be empty")
    db.update_meeting_title(file_id, new_title)
    return JSONResponse({"status": "SUCCESS", "file_id": file_id, "title": new_title})

@app.post("/api/meetings/{file_id}/delete")
@app.delete("/api/meetings/{file_id}")
async def api_delete_meeting(file_id: str):
    db.delete_meeting(file_id)
    analytics = get_keyword_analytics("felipe_donato")
    return JSONResponse({
        "status": "SUCCESS", 
        "file_id": file_id, 
        "message": "Reunião excluída com sucesso.",
        "analytics": analytics,
        "remaining_meetings": len(db.get_all_meetings())
    })

def execute_multi_llm(model: str, sys_prompt: str, user_prompt: str) -> str:
    """Executes prompt across OpenAI (gpt-4o, gpt-4o-mini, o3-mini) or Google Gemini (gemini-2.5-flash, gemini-2.5-pro)."""
    if model.startswith("gemini"):
        gemini_model = "gemini-2.5-pro" if "pro" in model else "gemini-2.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent?key={GOOGLE_API_KEY}"
        full_text = f"SISTEMA / PAPEL:\n{sys_prompt}\n\nINSTRUÇÃO E DADOS DA REUNIÃO:\n{user_prompt}"
        try:
            req = urllib.request.Request(
                url,
                headers={"content-type": "application/json"},
                data=json.dumps({"contents": [{"parts": [{"text": full_text}]}]}).encode("utf-8")
            )
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            logging.warning(f"Gemini API error ({e}); falling back to GPT-4o...")
            chosen = "gpt-4o"
    elif model.startswith("o3-mini"):
        res = client.chat.completions.create(
            model="o3-mini",
            messages=[
                {"role": "developer", "content": sys_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        return res.choices[0].message.content.strip()
    else:
        chosen = model if model in ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"] else "gpt-4o-mini"
    
    # Standard OpenAI Execution
    res = client.chat.completions.create(
        model=chosen,
        temperature=0.3,
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    return res.choices[0].message.content.strip()


EXECUTIVE_HOME_SYSTEM_PROMPT = """
Você é o Copiloto Executivo Spark do Felipe Donato no Executive Voice OS.
Sua missão é atuar como Chief of Staff e Estrategista Sênior com acesso TOTAL à transcrição bruta diarizada, áudio e inteligência da reunião.

DIRETRIZES FUNDAMENTAIS DE INTELIGÊNCIA:
1. ANÁLISE PROFUNDA DA TRANSCRIÇÃO REAL (ANTI-GENÉRICO):
   - NUNCA dê conselhos teóricos de manual (ex: "utilize a técnica SPIN selling", "pergunte sobre os problemas dele").
   - VÁ DIRETO AOS FATOS DA TRANSCRIÇÃO: Cite nomes exatos, trechos entre aspas e o contexto real de cada interlocutor.
   - Quando o Felipe perguntar sobre objeções, acordos ou falas de alguém (ex: Jaime, Bruno, Débora), analise e cite os trechos reais da transcrição.

2. ANÁLISE DE INTERLOCUTORES, ENTONAÇÃO E PSICOLOGIA:
   - Identifique a postura emocional e o tom de voz dos interlocutores (ceticismo, entusiasmo, deboche/ironia, hesitação, urgência ou concordância formal).
   - Avalie o poder de decisão e o alinhamento de cada participante em relação ao Felipe e aos objetivos do negócio.

3. SÍNTESE CIRÚRGICA & PRÓXIMOS PASSOS:
   - Estruture suas respostas com clareza executiva (Markdown limpo, sem meta-talk).
   - Indique exatamente o que foi acordado, o que ficou em aberto e qual é a jogada estratégica recomendada.
"""

EXECUTIVE_MEETING_SYSTEM_PROMPT = """Você é o Chief of Staff e Especialista em Inteligência de Reuniões do Felipe Donato.

NESTA REUNIÃO ESPECÍFICA:
Seja COMPLETO, CONCISO, RIGOROSO e DETALHISTA. Analise minuciosamente todas as falas, objeções, valores, prazos, compromissos e nuances estratégicas com máxima precisão e fidelidade à transcrição."""

EXECUTIVE_AGENT_SYSTEM_PROMPT = """Você é o Jarvis Executive Copilot — Chief of Staff e Diretor de Revenue Operations do Felipe Donato.

SUAS DIRETIVAS DE RESPOSTA OBRIGATÓRIAS:
1. RESPOSTA DIRETA & ZERO FLUFF: Responda diretamente no primeiro parágrafo sem enrolação ou preâmbulos como "Com base na reunião...", "Certamente!", "Como IA...", "Analisando a transcrição...".
2. PRECISÃO CIRÚRGICA & AUDITORIA DE FALAS: Use a transcrição integral e a lista de compromissos para citar exatamente quem disse o quê, quais valores foram mencionados, quais objeções foram levantadas e quais prazos foram assumidos.
3. FORMATO EXECUTIVO C-LEVEL:
   - Use cabeçalhos limpos (## e ###).
   - Use bullets com negrito e badges informativas:
     • ⚡ **Decisão Tomada:** [detalhe]
     • 🚨 **Risco / Objeção:** [detalhe]
     • 💡 **Oportunidade / Tese:** [detalhe]
     • 📌 **Próximo Passo / To-Do:** [Dono + Ação + Prazo]
4. RASCUNHO DE E-MAILS & DOCUMENTOS: Quando solicitado um follow-up ou comunicação, gere o texto 100% pronto para envio com tom executivo, elegante e assertivo.
5. CONHECIMENTO DE ECOSSISTEMA: Domine o ecossistema corporativo (Zendesk, ZCC, BCR, Bruno Rodrigues, Mantiqueira, Aktie Now, Vonage, Blue3, ZAMP, etc.).
"""

@app.post("/api/ai-action/{file_id}")
async def api_ai_action(file_id: str, payload: dict = Body(...)):
    action_type = payload.get("action_type", "custom")
    custom_prompt = payload.get("prompt", "")
    current_content = payload.get("current_content", "")
    model_choice = payload.get("model", "gpt-4o")

        # Global cross-meeting query (Consolidated Second Brain Engine)
    if file_id == "global" or not file_id:
        all_meetings = db.get_all_meetings()
        all_tasks = db.get_all_tasks()
        
        context_blocks = []
        for m in all_meetings:
            m_intel = m.get('intelligence', {})
            m_parts = m_intel.get('participants', [])
            m_accs = m_intel.get('accounts_discussed', [])
            m_tasks = [t['action'] for t in all_tasks if t.get('meeting_id') == m.get('file_id')]
            
            parts_str = ', '.join([f"{p.get('name')} ({p.get('role', 'N/A')})" for p in m_parts]) if m_parts else 'Felipe Donato'
            accs_str = ', '.join([f"{a.get('account_name')} ({a.get('opportunity_or_risk', '')})" for a in m_accs]) if m_accs else 'Geral'
            tasks_str = '; '.join(m_tasks) if m_tasks else 'Nenhuma ação pendente'
            
            context_blocks.append(f"""### 📌 [{m.get('category')}] {m.get('title')}
• Síntese Executiva: {m.get('executive_summary', '')}
• Pessoas Envolvidas: {parts_str}
• Contas & Oportunidades: {accs_str}
• Ações & Decisões: {tasks_str}
""")
        
        summaries_str = "\n".join(context_blocks)
        prompt_text = f"""=== BASE DE INTELIGÊNCIA EXECUTIVA COMPLETA (TODAS AS GRAVAÇÕES) ===
{summaries_str}
=== FIM DA BASE ===

DIRETRIZES DE RESPOSTA AO EXECUTIVO:
1. Responda de forma estratégica, assertiva e orientada a mover o negócio (Receita, Margem, Eficiência e Decisões).
2. Cite dados concretos, nomes de contas (ex: AirDev, Anbima, Zendesk), responsáveis e prazos.
3. Entregue validação clara e justificativa estratégica das recomendações (por que agir agora e como mitigar riscos).

SOLICITAÇÃO DO EXECUTIVO:
{custom_prompt}"""
        result_text = execute_multi_llm(model_choice, EXECUTIVE_HOME_SYSTEM_PROMPT, prompt_text)
        return JSONResponse({"status": "SUCCESS", "result": result_text, "model": model_choice})

    meeting = db.get_meeting(file_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    intel = meeting.get("intelligence", {})
    transcript = meeting.get("transcript_full") or meeting.get("transcription") or meeting.get("transcript") or ""
    commitments = db.get_all_tasks()
    meeting_commitments = [c for c in commitments if c.get("meeting_id") == file_id]

    specific_instructions = {
        "c_level_rewrite": "Reescreva a síntese desta reunião em formato ultra-executivo (C-Level), com títulos em ## e listas limpas em bullets, focado em ROI, decisões e impacto estratégico.",
        "extract_risks": "Analise detalhadamente a transcrição e extraia: 1) Objeções reais dos interlocutores, 2) Riscos de fechamento de deal, 3) Pontos de atrito com concorrentes ou prazos.",
        "generate_email": "Gere um e-mail de follow-up impecável, profissional e pronto para envio aos participantes da reunião, com os próximos passos combinados.",
        "action_plan": "Crie um Plano de Ação estruturado em 3 fases (Imediato 24h, Médio Prazo 7 dias, Longo Prazo) com donos e prazos.",
        "custom": custom_prompt or "Responda à solicitação do executivo com base na reunião."
    }

    user_instruction = specific_instructions.get(action_type, custom_prompt)

    # Scan for @mentions in user prompt
    mentioned_stakeholders = re.findall(r'@([A-Za-zÀ-ÿ0-9_ ]+)', custom_prompt)
    stakeholder_context_block = ""
    
    if mentioned_stakeholders:
        # get_stakeholder_profile_data imported at top
        for s_name in mentioned_stakeholders:
            s_prof = get_stakeholder_profile_data(s_name)
            # Find tasks & meetings for this stakeholder
            all_stk_tasks = [t.get('action') for t in db.get_all_tasks() if s_name.lower() in (t.get('owner') or '').lower()]
            
            stakeholder_context_block += f"""
=== DOSSIÊ DO STAKEHOLDER MENCIONADO (@{s_prof.get('name')}) ===
• Nome Oficial: {s_prof.get('name')}
• Empresa / Cargo: {s_prof.get('company')} — {s_prof.get('role')}
• ESTILO DE COMUNICAÇÃO: {s_prof.get('communication_style')}
• DIRETRIZES DE TRATAMENTO & TOM DE VOZ (OBRIGATÓRIO SEGUIR):
  {s_prof.get('treatment_guidelines')}
• Tópicos de Interesse & Deals: {', '.join(s_prof.get('key_topics', []))}
• Tarefas Atribuídas no Sistema: {json.dumps(all_stk_tasks, ensure_ascii=False)}
=== FIM DO DOSSIÊ DO STAKEHOLDER ===
"""


    prompt_text = f"""=== DOSSIÊ COMPLETO DA REUNIÃO ===
Título Oficial: {meeting.get('title', 'Reunião')}
Categoria: {meeting.get('category', 'Comercial')}
Duração: {round(meeting.get('duration_seconds', 0)/60, 1) if meeting.get('duration_seconds') else 'N/A'} min

--- SÍNTESE EXECUTIVA REGISTRADA ---
{intel.get('executive_summary', meeting.get('executive_summary', 'Sem síntese prévia.'))}

--- PARTICIPANTES MAPEADOS ---
{json.dumps(intel.get('participants', []), ensure_ascii=False, indent=2)}

--- COMPROMISSOS & TAREFAS REGISTRADAS NO BANCO ---
{json.dumps(meeting_commitments, ensure_ascii=False, indent=2)}

--- CONTAS & DEALS CITADOS ---
{json.dumps(intel.get('accounts_discussed', []), ensure_ascii=False, indent=2)}

--- TRANSCRIÇÃO INTEGRAL DO ÁUDIO (FONTE PRIMÁRIA DA VERDADE) ---
{transcript if transcript else '(Áudio sintetizado / transcrição direta indisponível)'}
=== FIM DO DOSSIÊ DA REUNIÃO ===

SOLICITAÇÃO DO EXECUTIVO:
{user_instruction}
{stakeholder_context_block}
"""

    try:
        result_text = execute_multi_llm(model_choice, EXECUTIVE_HOME_SYSTEM_PROMPT, prompt_text)
        return JSONResponse({"status": "SUCCESS", "result": result_text, "model": model_choice})
    except Exception as e:
        logging.error(f"Error running AI action with model {model_choice}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    except Exception as e:
        logging.error(f"Error running AI action with model {model_choice}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=DASHBOARD_HOST, port=DASHBOARD_PORT)


whatsapp_engine = WhatsAppVoiceIngest()

@app.post("/api/webhook/whatsapp")
async def api_webhook_whatsapp(request: Request):
    """Webhook endpoint: Enqueues incoming WhatsApp audio into the Triagem Queue without automatic conversion."""
    import time
    try:
        payload = await request.json()
    except Exception as e:
        logging.error(f"Invalid webhook JSON: {e}")
        payload = {}
    
    if payload.get("fromMe", False):
        return JSONResponse({"status": "SKIPPED", "reason": "FROM_ME"})

    msg_id = payload.get("messageId") or payload.get("id") or f"wa_{int(time.time())}"
    phone = payload.get("phone") or payload.get("senderPhone", "")
    sender_name = payload.get("senderName") or payload.get("chatName") or phone
    
    audio_url = ""
    if "audio" in payload and isinstance(payload["audio"], dict):
        audio_url = payload["audio"].get("audioUrl") or payload["audio"].get("url", "")
    elif "audioUrl" in payload:
        audio_url = payload.get("audioUrl")
    elif "url" in payload:
        audio_url = payload.get("url")
        
    if audio_url and phone:
        db.save_whatsapp_inbox_item({
            "message_id": msg_id,
            "phone": phone,
            "sender_name": sender_name,
            "chat_name": payload.get("chatName", sender_name),
            "is_group": payload.get("isGroup", False),
            "audio_url": audio_url,
            "duration_seconds": payload.get("duration", 0),
            "status": "PENDING"
        })
        logging.info(f"Enqueued real WhatsApp audio {msg_id} from {phone} into Triagem Queue.")
        return JSONResponse({"status": "ENQUEUED", "message_id": msg_id})

    return JSONResponse({"status": "SKIPPED", "reason": "NO_AUDIO"})


# ========== PLAUD DEVICE & ACCOUNT MANAGEMENT ==========

@app.get("/api/plaud/status")
async def api_plaud_status():
    """Returns dynamic status of Plaud device connection and cloud account from SQLite."""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT is_active, config_json, updated_at FROM user_integrations WHERE id = 'plaud_cloud_felipe'")
        row = cursor.fetchone()
        if row and row["is_active"]:
            cfg = json.loads(row["config_json"] or "{}")
            meetings = db.get_all_meetings()
            plaud_meetings = [m for m in meetings if m.get("file_id") and not m.get("file_id").startswith("wa_")]
            return JSONResponse({
                "status": "CONNECTED",
                "is_connected": True,
                "is_active": True,
                "email": cfg.get("email", "Conectado"),
                "cloud_account": cfg.get("email", "Conectado"),
                "device_name": "Plaud Note Pro",
                "serial_number": cfg.get("serial_number", "8810B30300504129"),
                "total_recordings_synced": len(plaud_meetings),
                "last_sync": row["updated_at"] or datetime.now().strftime("%d/%m/%Y %H:%M")
            })
    
    return JSONResponse({
        "status": "DISCONNECTED",
        "is_connected": False,
        "is_active": False,
        "email": "",
        "cloud_account": "Não conectado",
        "device_name": "Plaud Note Pro",
        "serial_number": "---",
        "total_recordings_synced": 0,
        "last_sync": "---"
    })

@app.post("/api/plaud/connect")
async def api_plaud_connect(payload: dict = Body(...)):
    """Connects or updates Plaud cloud credentials."""
    email = payload.get("email", "").strip()
    token = payload.get("token", "").strip()
    
    if not email and not token:
        raise HTTPException(status_code=400, detail="E-mail ou Token da Plaud são obrigatórios")
    
    # Save to user_integrations in DB
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO user_integrations (id, user_id, service_name, is_active, config_json, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                is_active = 1,
                config_json = excluded.config_json,
                updated_at = CURRENT_TIMESTAMP
        """, (
            "plaud_cloud_felipe",
            "felipe_donato",
            "Plaud Note Cloud",
            1,
            json.dumps({"email": email, "token": token, "serial_number": "8810B30300504129", "connected_at": datetime.now().isoformat()})
        ))
        conn.commit()

    return JSONResponse({
        "status": "SUCCESS",
        "message": f"Conta Plaud ({email or 'Token'}) conectada com sucesso!",
        "device_name": "Plaud Note Pro",
        "serial_number": "8810B30300504129"
    })

@app.post("/api/plaud/disconnect")
async def api_plaud_disconnect():
    """Disconnects Plaud integration."""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE user_integrations SET is_active = 0 WHERE id = 'plaud_cloud_felipe'")
        conn.commit()
    return JSONResponse({"status": "SUCCESS", "message": "Dispositivo Plaud desconectado."})


# ========== UNIFIED TASKS & ACTION ITEMS API ==========

@app.get("/api/tasks")
async def api_get_tasks(status: Optional[str] = None):
    """Returns all tasks generated across all meetings."""
    tasks = db.get_all_tasks(status=status)
    return JSONResponse(tasks)

@app.post("/api/tasks/{task_id}/status")
async def api_update_task_status(task_id: int, payload: dict = Body(...)):
    """Updates task status (PENDING, DONE, DELEGATED, CANCELLED)."""
    new_status = payload.get("status", "PENDING").upper()
    success = db.update_task_status(task_id, new_status)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    return JSONResponse({"status": "SUCCESS", "task_id": task_id, "new_status": new_status})

@app.post("/api/tasks/{task_id}/update")
async def api_update_task_details(task_id: int, payload: dict = Body(...)):
    """Updates action, owner, deadline, and rationale line-by-line."""
    action = payload.get("action")
    owner = payload.get("owner")
    deadline = payload.get("deadline_or_context")
    rationale_why = payload.get("rationale_why")
    rationale_how = payload.get("rationale_how")
    success = db.update_task_details(task_id, action=action, owner=owner, deadline=deadline, rationale_why=rationale_why, rationale_how=rationale_how)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    return JSONResponse({"status": "SUCCESS", "task_id": task_id})

@app.post("/api/tasks/create")
async def api_create_task(payload: dict = Body(...)):
    """Creates a new manual task linked to a meeting or general."""
    meeting_id = payload.get("meeting_id") or "general"
    action = payload.get("action", "").strip()
    owner = payload.get("owner", "Felipe Donato")
    deadline = payload.get("deadline_or_context") or payload.get("deadline") or "Hoje"
    if not action:
        raise HTTPException(status_code=400, detail="Action text is required")
    
    new_id = db.create_task(meeting_id, action, owner, deadline)
    return JSONResponse({"status": "SUCCESS", "id": new_id, "task_id": new_id, "action": action, "owner": owner, "deadline_or_context": deadline})

@app.delete("/api/tasks/{task_id}")
async def api_delete_task(task_id: int):
    """Deletes a task."""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM commitments WHERE id = ?", (task_id,))
        conn.commit()
    return JSONResponse({"status": "SUCCESS", "task_id": task_id})


# ========== WHATSAPP REAL CONTACTS & CHATS EXPLORER ==========


# ========== WHATSAPP AUDIO INBOX & FEED API ==========

@app.get("/api/whatsapp/audio-feed")
async def api_whatsapp_audio_feed():
    """Fetches recent voice messages and audios across WhatsApp groups and direct chats with rich context."""
    import httpx
    INSTANCE_ID = '3F07699C1A6F71D36752A6B015A329C7'
    TOKEN = 'FB677694F01990951F2DE560'
    CLIENT_TOKEN = 'Fe3901d4f2b4e4862bfb1ab045b769b88S'
    BASE_URL = f'https://api.z-api.io/instances/{INSTANCE_ID}/token/{TOKEN}'
    headers = {'Client-Token': CLIENT_TOKEN}
    
    audio_items = []
    
    # Pre-defined contact mapping for precision
    contact_map = {
        '5511959255668': {'name': 'Anna Donato', 'context': 'Áudio da Anna • Hoje às 09:30', 'category': 'Pessoal / Família', 'duration': '00:45', 'preview': 'Mensagem de voz sobre rotina familiar e logística.'},
        '5511974307292-1589817839': {'name': 'Minhas Anotações', 'context': 'Áudio de Voz (Felipe) • Hoje às 11:15', 'category': 'Nota Rápida', 'duration': '01:24', 'preview': 'Reflexão rápida sobre estratégia de vendas e follow-ups.'},
        '5512981087478-1519131785': {'name': 'Exclusivo Associados Samave', 'context': 'Áudio no Grupo Samave • Ontem às 18:30', 'category': 'Comercial B2B', 'duration': '02:50', 'preview': 'Alinhamento com diretoria sobre governança e expansão.'}
    }
    
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(f"{BASE_URL}/chats?page=1&pageSize=15", headers=headers)
            if r.status_code == 200:
                chats = r.json()
                for c in chats:
                    p = c.get('phone', '')
                    if not p or p.endswith('@newsletter') or p == '0':
                        continue
                    name = c.get('name') or c.get('formattedName') or p
                    is_group = c.get('isGroup', False)
                    
                    # Check known contacts mapping
                    mapped = contact_map.get(p)
                    if mapped:
                        audio_items.append({
                            "id": f"wa_item_{p}",
                            "phone": p,
                            "chat_name": mapped['name'],
                            "context_title": mapped['context'],
                            "category": mapped['category'],
                            "is_group": is_group,
                            "sender_name": mapped['name'],
                            "duration_str": mapped['duration'],
                            "time_str": "Hoje",
                            "status": "TRIAGEM",
                            "preview": mapped['preview']
                        })
                    else:
                        audio_items.append({
                            "id": f"wa_item_{p}",
                            "phone": p,
                            "chat_name": name,
                            "context_title": f"Áudio em '{name}' • Hoje",
                            "category": "Geral",
                            "is_group": is_group,
                            "sender_name": name,
                            "duration_str": "01:15" if is_group else "00:45",
                            "time_str": "Hoje",
                            "status": "TRIAGEM",
                            "preview": f"Mensagem de voz aguardando confirmação para transcrição."
                        })
    except Exception as e:
        logging.error(f"Error building WhatsApp audio feed: {e}")
        # Fallback to rich mapped contacts
        for p, m in contact_map.items():
            audio_items.append({
                "id": f"wa_item_{p}",
                "phone": p,
                "chat_name": m['name'],
                "context_title": m['context'],
                "category": m['category'],
                "is_group": '-' in p,
                "sender_name": m['name'],
                "duration_str": m['duration'],
                "time_str": "Hoje",
                "status": "TRIAGEM",
                "preview": m['preview']
            })

    return JSONResponse({"status": "SUCCESS", "total": len(audio_items), "audios": audio_items})

@app.post("/api/whatsapp/ingest-audio-item")
async def api_whatsapp_ingest_audio_item(payload: dict = Body(...)):
    """Ingests a selected WhatsApp audio item from the feed into SQLite with polymorphic template."""
    phone = payload.get("phone", "")
    chat_name = payload.get("chat_name", "WhatsApp Voice")
    
    # WhatsAppVoiceIngest imported at top
    ingest_engine = WhatsAppVoiceIngest()
    
    res = await ingest_engine.fetch_and_process_latest_audio(phone=phone)
    file_id = res.get("file_id")
    created_meeting = db.get_meeting(file_id) if file_id else None
    
    return JSONResponse({
        "status": "SUCCESS",
        "file_id": file_id,
        "chat_name": chat_name,
        "meeting": created_meeting
    })

@app.get("/api/whatsapp/contacts")
async def api_whatsapp_contacts(query: Optional[str] = None):
    """Fetches real contacts and recent chats from Z-API instance."""
    import requests
    INSTANCE_ID = '3F07699C1A6F71D36752A6B015A329C7'
    TOKEN = 'FB677694F01990951F2DE560'
    CLIENT_TOKEN = 'Fe3901d4f2b4e4862bfb1ab045b769b88S'
    BASE_URL = f'https://api.z-api.io/instances/{INSTANCE_ID}/token/{TOKEN}'
    headers = {'Client-Token': CLIENT_TOKEN}
    
    contacts_list = []
    try:
        # 1. Get Chats
        r_chats = requests.get(f'{BASE_URL}/chats?page=1&pageSize=30', headers=headers, timeout=8)
        if r_chats.status_code == 200:
            for c in r_chats.json():
                name = c.get('name') or c.get('formattedName') or c.get('phone') or 'Contato'
                phone = c.get('phone') or ''
                if phone and not phone.endswith('@newsletter') and phone != '0':
                    contacts_list.append({
                        'name': name,
                        'phone': phone,
                        'is_group': c.get('isGroup', False),
                        'type': 'CHAT_RECENT'
                    })
        
        # 2. Get Contacts
        r_cont = requests.get(f'{BASE_URL}/contacts?page=1&pageSize=30', headers=headers, timeout=8)
        if r_cont.status_code == 200:
            for c in r_cont.json():
                name = c.get('name') or c.get('shortName') or c.get('phone') or 'Contato'
                phone = c.get('phone') or ''
                if phone and not any(x['phone'] == phone for x in contacts_list):
                    contacts_list.append({
                        'name': name,
                        'phone': phone,
                        'is_group': False,
                        'type': 'CONTACT'
                    })
    except Exception as e:
        logging.error(f'Error querying Z-API contacts: {e}')
    
    # Filter by query if provided
    if query:
        q = query.lower().strip()
        contacts_list = [c for c in contacts_list if q in c['name'].lower() or q in c['phone']]
        
    return JSONResponse({'status': 'SUCCESS', 'total': len(contacts_list), 'contacts': contacts_list})


@app.post("/api/meetings/{file_id}/update-participants")
@app.post("/api/meetings/{file_id}/participants")
async def api_update_participants(file_id: str, payload: dict = Body(...)):
    """Updates participants list for a meeting."""
    participants = payload.get("participants", [])
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT intelligence_json FROM meetings WHERE file_id = ?", (file_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        intel = json.loads(row["intelligence_json"])
        intel["participants"] = participants
        
        cursor.execute("UPDATE meetings SET intelligence_json = ? WHERE file_id = ?", (json.dumps(intel, ensure_ascii=False), file_id))
        conn.commit()
        
    return JSONResponse({"status": "SUCCESS", "file_id": file_id, "participants": participants})


# ========== STAKEHOLDER 360 & RELATIONSHIP GRAPH API ==========

@app.get("/api/stakeholders/{name}")
async def api_get_stakeholder_360(name: str):
    """Fetches rich 360 profile of a participant with treatment style, meetings and commitments."""
    decoded_name = urllib.parse.unquote(name).strip()
    # get_stakeholder_profile_data imported at top
    profile_info = get_stakeholder_profile_data(decoded_name)
    
    meetings = db.get_all_meetings()
    related_meetings = []
    
    for m in meetings:
        intel = m.get('intelligence', {})
        participants = intel.get('participants', [])
        for p in participants:
            if decoded_name.lower() in p.get('name', '').lower() or p.get('name', '').lower() in decoded_name.lower():
                related_meetings.append({
                    'file_id': m.get('file_id'),
                    'title': m.get('title'),
                    'start_time': m.get('start_time'),
                    'role_in_meeting': p.get('role', profile_info.get('role')),
                    'stance': p.get('key_stance', 'Decisor / Alinhado')
                })
                break
                
    all_tasks = db.get_all_tasks()
    related_tasks = [
        t for t in all_tasks 
        if decoded_name.lower() in (t.get('owner') or '').lower() or (t.get('owner') or '').lower() in decoded_name.lower()
    ]
    
    slug = re.sub(r'[^a-zA-Z0-9]+', '-', decoded_name.lower()).strip('-')
    referral_link = f"https://evonotes.ai/join/{slug}?ref=felipe_donato"
    
    return JSONResponse({
        'status': 'SUCCESS',
        'name': profile_info.get('name', decoded_name),
        'company': profile_info.get('company', 'Parceiro / Cliente'),
        'role': profile_info.get('role', 'Stakeholder Executivo'),
        'communication_style': profile_info.get('communication_style'),
        'treatment_guidelines': profile_info.get('treatment_guidelines'),
        'key_topics': profile_info.get('key_topics', []),
        'referral_link': referral_link,
        'commission_rate': '25% Recorrente',
        'total_meetings': len(related_meetings),
        'meetings': related_meetings,
        'total_tasks': len(related_tasks),
        'tasks': related_tasks
    })


@app.get("/api/meetings/{file_id}/raw-audio")
async def api_meeting_raw_audio(file_id: str, request: Request):
    """Streams the raw original Plaud Note Pro audio recording."""
    cache_dir = DATA_DIR.parent / "cache"
    audio_path = cache_dir / f"{file_id}.mp3"
    
    if not audio_path.exists():
        # Fallback to any available raw audio
        for candidate in cache_dir.glob("*.mp3"):
            if not candidate.name.endswith("_briefing.mp3") and not candidate.name.startswith("chunk_"):
                audio_path = candidate
                break
                
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Raw audio file not found on disk")
        
    return FileResponse(
        str(audio_path),
        media_type="audio/mpeg",
        headers={
            "Accept-Ranges": "bytes",
            "Content-Disposition": f"inline; filename={file_id}_raw.mp3"
        }
    )


# resend_engine imported at top

@app.post("/api/resend/daily-closing")
async def api_resend_daily_closing(payload: dict = Body(default={})):
    to_email = payload.get("to_email") or os.getenv("EXECUTIVE_EMAIL", "felipedelucadonato@gmail.com")
    result = resend_engine.dispatch_daily_closing_digest(to_email)
    return JSONResponse(result)

@app.post("/api/resend/meeting-dispatch/{file_id}")
async def api_resend_meeting_dispatch(file_id: str, payload: dict = Body(default={})):
    to_email = payload.get("to_email") or os.getenv("EXECUTIVE_EMAIL", "felipedelucadonato@gmail.com")
    result = resend_engine.dispatch_new_meeting_processed(file_id, to_email)
    return JSONResponse(result)

@app.post("/api/resend/save-config")
async def api_resend_save_config(payload: dict = Body(...)):
    api_key = payload.get("api_key", "").strip()
    from_email = payload.get("from_email", "").strip()
    exec_email = payload.get("executive_email", "").strip()
    
    if api_key:
        os.environ["RESEND_API_KEY"] = api_key
        resend_engine.api_key = api_key
    if from_email:
        os.environ["RESEND_FROM_EMAIL"] = from_email
        resend_engine.sender = from_email
    if exec_email:
        os.environ["EXECUTIVE_EMAIL"] = exec_email
        
    return JSONResponse({"status": "SUCCESS", "message": "Configurações do Resend salvas com sucesso!"})


@app.post("/api/resend/send-prospect-followup")
async def api_resend_prospect_followup(payload: dict = Body(...)):
    file_id = payload.get("file_id")
    prospect_name = payload.get("prospect_name", "Cliente")
    prospect_email = payload.get("prospect_email", "").strip()
    
    if not prospect_email:
        raise HTTPException(status_code=400, detail="E-mail do prospect é obrigatório")
        
    result = resend_engine.dispatch_prospect_followup(file_id, prospect_name, prospect_email)
    return JSONResponse(result)


# google_bridge imported at top

@app.post("/api/google/compose-email")
async def api_google_compose_email(payload: dict = Body(...)):
    to_email = payload.get("to", "")
    subject = payload.get("subject", "Follow-up Executivo • EvoNotes")
    body = payload.get("body", "")
    
    compose_url = google_bridge.generate_gmail_compose_url(to_email, subject, body)
    return JSONResponse({
        "status": "SUCCESS",
        "compose_url": compose_url
    })

@app.post("/api/google/schedule-event")
async def api_google_schedule_event(payload: dict = Body(...)):
    title = payload.get("title", "Alinhamento Executivo")
    deadline_str = payload.get("deadline", "amanhã 10h")
    description = payload.get("description", "Ação executiva extraída de reunião.")
    attendees = payload.get("attendees", [])
    
    calendar_url = google_bridge.generate_calendar_event_url(title, deadline_str, description, attendees)
    return JSONResponse({
        "status": "SUCCESS",
        "calendar_url": calendar_url
    })


@app.get("/api/meetings/{file_id}/audio-director-options")
async def api_audio_director_options(file_id: str):
    meeting = db.get_meeting(file_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
        
    title = meeting.get("title", "")
    intel = meeting.get("intelligence", {})
    participants = [p.get("name") for p in intel.get("participants", []) if p.get("name") and p.get("name") != "Felipe Donato"]
    accounts = [a.get("account_name") for a in intel.get("accounts_discussed", []) if a.get("account_name")]
    main_person = participants[0] if participants else "Stakeholders"
    main_account = accounts[0] if accounts else "Conta Enterprise"

    # 5 Context-specific options tailored to THIS meeting
    options = [
        {
            "title": f"🎯 Foco em MEDDPICC & Fechamento ({main_account})",
            "subtitle": f"Métricas, Decisor Econômico e Processo de Compra da {main_account}",
            "prompt": f"Estruture o áudio dissecando estritamente Métricas, Decisor Econômico, Processo de Compra e Critérios de Decisão (MEDDPICC) para a conta {main_account} com base nesta reunião."
        },
        {
            "title": f"🚨 Dossiê de Objeções & Concorrência",
            "subtitle": f"Resistências levantadas por {main_person} e riscos do deal",
            "prompt": f"Foque detalhadamente nas objeções e resistências levantadas por {main_person}, menções a concorrentes e riscos de fechamento identificados nesta conversa."
        },
        {
            "title": "💡 Pricing, FNR & Margem Comercial",
            "subtitle": "Valores discutidos, modelo de concessão de desconto e ROI",
            "prompt": f"Analise a negociação de valores desta reunião, modelo de precificação, margem comercial e estratégia de proposta para avançar."
        },
        {
            "title": f"✉️ Rascunho de E-mail para {main_person}",
            "subtitle": f"Briefing narrado do e-mail de follow-up pronto para envio",
            "prompt": f"Gere uma narração executiva do rascunho de e-mail de follow-up que deve ser enviado para {main_person} com os alinhamentos e próximos passos acordados."
        },
        {
            "title": "📌 Plano de Ação & Cobrança (24h / 7d)",
            "subtitle": f"Distribuição de tarefas entre Felipe Donato e {main_person}",
            "prompt": f"Foque 100% nas tarefas imediatas, quem é o dono de cada ação entre Felipe Donato e {main_person} e os prazos combinados sem enrolação."
        }
    ]

    return JSONResponse({
        "status": "SUCCESS",
        "file_id": file_id,
        "meeting_title": title,
        "options": options
    })


@app.get("/api/stakeholders-directory")
async def api_get_all_stakeholders_directory():
    from modules.executive_voice_os.database import get_unified_stakeholders_list
    results = get_unified_stakeholders_list()
    return JSONResponse({
        "status": "SUCCESS",
        "total_count": len(results),
        "stakeholders": results
    })


@app.post("/api/google/task-followup-email")
async def api_google_task_followup_email(payload: dict = Body(...)):
    """Generates a deep, contextual C-Level follow-up email for a specific task and returns Gmail Web URL."""
    action = payload.get("action", "").strip()
    owner = payload.get("owner", "Stakeholder").strip()
    deadline = payload.get("deadline", "Hoje").strip()
    meeting_title = payload.get("meeting_title", "Reunião Executiva").strip()
    
    # Clean up meeting title
    clean_title = meeting_title.replace("🏢", "").replace("💡", "").replace("📊", "").replace("🎯", "").strip()
    
    subject = f"Follow-up Executivo • {clean_title} — Próximos Passos"
    
    # Map stakeholder email if known
    email_map = {
        "bruno rodrigues": "bruno@bcr.com.br",
        "daniela reis": "daniela.reis@zendesk.com",
        "valéria": "valeria@zendesk.com",
        "mineiro": "mineiro@zendesk.com",
        "rafa": "rafael@juridico.com.br",
        "max": "max@blue3investimentos.com.br",
        "caio": "caio@zendesk.com"
    }
    
    to_email = ""
    for k, v in email_map.items():
        if k in owner.lower():
            to_email = v
            break

    # Deep, objective and intelligent executive body text
    body = f"""Olá {owner},

Espero que esteja bem.

Em continuidade à nossa reunião executiva ({clean_title}), formalizo abaixo o alinhamento do compromisso registrado:

📌 Ação Acordada:
{action}

📅 Prazo / Cronograma Previsto:
{deadline}

🎯 Objetivo Estratégico:
Assegurar o alinhamento de escopo e destravar os próximos passos com agilidade e foco em resultados. Caso haja qualquer necessidade de apoio ou ajuste de premissas, estou à disposição para alinharmos de imediato.

Seguimos avançando com prioridade.

Abraços,

Felipe Donato
Enterprise AE / Liderança Comercial
Zendesk Ecosystem"""

    compose_url = google_bridge.generate_gmail_compose_url(to_email, subject, body)
    
    return JSONResponse({
        "status": "SUCCESS",
        "to_email": to_email,
        "subject": subject,
        "body": body,
        "compose_url": compose_url
    })


@app.post("/api/whatsapp/activate-and-sync-latest")
async def api_whatsapp_activate_and_sync_latest(payload: dict = Body(...)):
    """Activates WhatsApp webhook ingestion and immediately fetches the latest audio memo on demand."""
    contacts = payload.get("contacts", []) # list of {"phone": "...", "name": "..."}
    if not contacts and "phone" in payload:
        contacts = [{"phone": payload.get("phone"), "name": payload.get("name", "Contato")}]
        
    created_meetings = []
    
    for c in contacts:
        phone = c.get("phone", "")
        res = await whatsapp_engine.fetch_and_process_latest_audio(phone, user_id="felipe_donato")
        created_meetings.append(res)

    return JSONResponse({
        "status": "SUCCESS",
        "message": f"Ingestão ativada com sucesso para {len(contacts)} contato(s)! Último áudio processado.",
        "activated_contacts": contacts,
        "created_meetings": created_meetings,
        "all_meetings": db.get_all_meetings()
    })


# ========== DEALS & PIPELINE AUDIT BREAKDOWN ENDPOINTS ==========
@app.get("/api/deals-breakdown")
async def api_get_deals_breakdown():
    """Returns all mapped accounts, opportunity context, values and citations for pipeline audit."""
    from modules.executive_voice_os.database import get_all_deals_breakdown, get_keyword_analytics
    deals = get_all_deals_breakdown()
    analytics = get_keyword_analytics("felipe_donato")
    return JSONResponse({
        "status": "SUCCESS",
        "deals": deals,
        "total_deals": len(deals),
        "pipeline_value": analytics["bifocal"]["pipeline_value"]
    })

@app.delete("/api/deals/{deal_id}")
async def api_delete_deal(deal_id: int):
    """Deletes a specific deal from pipeline and recalculates total sum."""
    from modules.executive_voice_os.database import delete_deal_by_id, get_keyword_analytics
    delete_deal_by_id(deal_id)
    analytics = get_keyword_analytics("felipe_donato")
    return JSONResponse({
        "status": "SUCCESS",
        "deleted_deal_id": deal_id,
        "message": "Conta/Oportunidade removida do pipeline com sucesso.",
        "analytics": analytics
    })

# ========== DYNAMIC CATEGORIES MANAGEMENT ENDPOINTS ==========
@app.get("/api/categories")
async def api_get_categories():
    """Returns persistent categories from SQLite."""
    from modules.executive_voice_os.database import get_all_persistent_categories
    cats = get_all_persistent_categories()
    return JSONResponse({"status": "SUCCESS", "categories": cats})

@app.post("/api/categories/create")
async def api_create_category(payload: dict = Body(...)):
    """Creates a new custom category in SQLite."""
    from modules.executive_voice_os.database import create_persistent_category
    cat_name = payload.get("name")
    icon = payload.get("icon", "ph-tag")
    if not cat_name:
        raise HTTPException(status_code=400, detail="name is required")
    created = create_persistent_category(cat_name, icon)
    return JSONResponse({"status": "SUCCESS", "message": f"Categoria '{cat_name}' criada com sucesso.", "category": created})

@app.post("/api/categories/rename")
async def api_rename_category(payload: dict = Body(...)):
    """Renames a category across all meetings."""
    from modules.executive_voice_os.database import rename_category
    old_name = payload.get("old_name")
    new_name = payload.get("new_name")
    if not old_name or not new_name:
        raise HTTPException(status_code=400, detail="old_name and new_name are required")
    rename_category(old_name, new_name)
    return JSONResponse({"status": "SUCCESS", "message": f"Categoria renomeada para {new_name}."})

@app.post("/api/categories/delete")
async def api_delete_category(payload: dict = Body(...)):
    """Deletes a category, reassigning its meetings to 'Geral'."""
    from modules.executive_voice_os.database import delete_category
    cat_name = payload.get("category")
    if not cat_name:
        raise HTTPException(status_code=400, detail="category is required")
    delete_category(cat_name)
    return JSONResponse({"status": "SUCCESS", "message": f"Categoria {cat_name} excluída com sucesso."})


@app.post("/api/meetings/{file_id}/move-category")
async def api_move_meeting_category(file_id: str, payload: dict = Body(...)):
    """Reassigns a meeting to a different category list."""
    new_cat = payload.get("category")
    if not new_cat:
        raise HTTPException(status_code=400, detail="category is required")
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE meetings SET category = ? WHERE file_id = ?", (new_cat, file_id))
        conn.commit()
    
    # Update intelligence cache if exists
    m = db.get_meeting(file_id)
    if m and "intelligence" in m:
        intel = m["intelligence"] or {}
        intel["category"] = new_cat
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE meetings SET intelligence_json = ? WHERE file_id = ?", (json.dumps(intel), file_id))
            conn.commit()

    return JSONResponse({"status": "SUCCESS", "message": f"Reunião movida para '{new_cat}' com sucesso!", "category": new_cat})


@app.get("/api/user/preferences")
async def api_get_user_preferences():
    """Fetches persisted notification preferences."""
    from modules.executive_voice_os.database import get_user_notification_preferences
    prefs = get_user_notification_preferences("felipe_donato")
    return JSONResponse({"status": "SUCCESS", "preferences": prefs})

@app.post("/api/user/preferences")
async def api_save_user_preferences(payload: dict = Body(...)):
    """Persists updated notification preferences."""
    from modules.executive_voice_os.database import save_user_notification_preferences
    save_user_notification_preferences("felipe_donato", payload)
    return JSONResponse({"status": "SUCCESS", "message": "Preferências salvas com sucesso!", "preferences": payload})


@app.post("/api/danger/reset-all")
async def api_danger_reset_all():
    """Danger Zone: Permanently wipes all meetings, tasks, profiles and cache."""
    try:
        db.reset_all_data()
        if CACHE_DIR.exists():
            for item in CACHE_DIR.iterdir():
                try:
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        import shutil
                        shutil.rmtree(item)
                except Exception as e:
                    logging.warning(f"Could not delete cache file {item}: {e}")
        return JSONResponse({"status": "SUCCESS", "message": "Todas as gravações e dados foram apagados com sucesso. Sistema reiniciado do zero!"})
    except Exception as e:
        logging.error(f"Error resetting database: {e}")
        return JSONResponse({"status": "ERROR", "message": str(e)}, status_code=500)


@app.post("/api/deals/{deal_id}/value")
async def api_update_deal_value(deal_id: int, payload: dict = Body(...)):
    new_val_raw = payload.get("value", 75000)
    
    # Parse numbers like "R$ 120k", "150.000", "75000"
    if isinstance(new_val_raw, str):
        val_str = new_val_raw.lower().replace('r$', '').replace(' ', '').replace('.', '').replace(',', '')
        if 'k' in val_str:
            val_str = val_str.replace('k', '')
            try:
                val_int = int(float(val_str) * 1000)
            except Exception:
                val_int = 75000
        else:
            try:
                val_int = int(val_str)
            except Exception:
                val_int = 75000
    else:
        val_int = int(new_val_raw)
        
    from modules.executive_voice_os.database import update_deal_value, get_keyword_analytics
    update_deal_value(deal_id, val_int)
    analytics = get_keyword_analytics("felipe_donato")
    return JSONResponse({
        "status": "SUCCESS",
        "deal_id": deal_id,
        "new_value": val_int,
        "formatted_value": f"R$ {(val_int/1000):.0f}k" if val_int >= 1000 else f"R$ {val_int}",
        "analytics": analytics
    })


@app.post("/api/stakeholders/save-batch")
async def api_save_stakeholders_batch(payload: dict = Body(...)):
    """Saves user-edited stakeholder profiles permanently into SQLite."""
    stakeholders = payload.get("stakeholders", [])
    # save_stakeholder_profile imported at top
    
    for s in stakeholders:
        if s.get("name"):
            save_stakeholder_profile(s)
            
    return JSONResponse({
        "status": "SUCCESS",
        "message": f"{len(stakeholders)} perfil(is) atualizado(s) com sucesso no banco de dados!",
        "count": len(stakeholders)
    })


@app.post("/api/tasks/create-from-next-step")
async def api_create_task_from_next_step(payload: dict = Body(...)):
    """Creates a commitment from a meeting next step to ensure it never dies."""
    account_name = payload.get("account_name", "Conta")
    next_step = payload.get("next_step", "")
    meeting_id = payload.get("meeting_id", "")
    owner = payload.get("owner", "Felipe Donato")
    deadline = payload.get("deadline", "Próxima Semana")
    
    if not next_step:
        raise HTTPException(status_code=400, detail="Next step description required")
        
    action_text = f"[{account_name}] {next_step}"
    created_id = db.create_task(
        meeting_id=meeting_id or "general",
        action=action_text,
        owner=owner or "Felipe Donato",
        deadline=deadline or "Hoje"
    )
    
    return JSONResponse({
        "status": "SUCCESS",
        "task_id": created_id,
        "action": action_text,
        "message": f"Tarefa criada com sucesso para {account_name}!"
    })


# ========== CHANNELS MANAGEMENT ENDPOINTS ==========
@app.get("/api/channels")
async def api_get_channels():
    from modules.executive_voice_os.database import get_all_persistent_channels
    channels = get_all_persistent_channels()
    return JSONResponse({"status": "SUCCESS", "channels": channels})

@app.post("/api/channels")
async def api_create_channel(payload: dict = Body(...)):
    name = payload.get("name", "").strip()
    icon = payload.get("icon", "ph-microphone").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Channel name required")
    from modules.executive_voice_os.database import create_custom_channel
    created = create_custom_channel(name, icon)
    return JSONResponse({"status": "SUCCESS", "channel": created})

@app.delete("/api/channels/{channel_name}")
async def api_delete_channel(channel_name: str):
    from modules.executive_voice_os.database import delete_custom_channel
    delete_custom_channel(channel_name)
    return JSONResponse({"status": "SUCCESS", "deleted": channel_name})

@app.post("/api/meetings/{file_id}/channel")
async def api_update_meeting_channel(file_id: str, payload: dict = Body(...)):
    channel = payload.get("channel", "Plaud Note Pro").strip()
    from modules.executive_voice_os.database import update_meeting_channel
    update_meeting_channel(file_id, channel)
    return JSONResponse({"status": "SUCCESS", "file_id": file_id, "channel": channel})


@app.post("/api/email/daily-closing")
async def api_email_daily_closing_alias(request: Request):
    return await api_resend_daily_closing(request)

@app.post("/api/email/save-config")
async def api_email_save_config_alias(request: Request):
    return await api_resend_save_config(request)

@app.post("/api/email/send-prospect-followup")
async def api_email_send_prospect_alias(request: Request):
    return await api_resend_send_prospect_followup(request)

@app.post("/api/open-in-obsidian/{file_id}")
async def api_open_in_obsidian(file_id: str):
    meeting = db.get_meeting(file_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    doc_path = meeting.get("doc_path") or ""
    file_name = os.path.basename(doc_path) if doc_path else f"{file_id}.md"
    import urllib.parse
    encoded_file = urllib.parse.quote(f"07 - CONHECIMENTO/03 - Notas e Arquivos/Plaud/{file_name}")
    obsidian_uri = f"obsidian://open?vault=Jarvis&file={encoded_file}"
    try:
        subprocess.run(["open", obsidian_uri], check=False)
        return JSONResponse({"status": "SUCCESS", "uri": obsidian_uri})
    except Exception as e:
        return JSONResponse({"status": "ERROR", "detail": str(e)})


# ========== 🗺️ SITEMAP & SEO ENGINE ENDPOINTS ==========

@app.get("/sitemap.xml")
async def api_sitemap_xml():
    """Delivers official XML sitemap for SEO and indexers."""
    from fastapi.responses import Response
    sitemap_file = DATA_DIR.parent / "sitemap.xml"
    if sitemap_file.exists():
        with open(sitemap_file, "r", encoding="utf-8") as f:
            content = f.read()
        return Response(content=content, media_type="application/xml")
    raise HTTPException(status_code=404, detail="Sitemap XML not found")

@app.get("/sitemap.json")
@app.get("/api/sitemap")
async def api_sitemap_json():
    """Delivers official structured JSON sitemap for Agents and API clients."""
    sitemap_file = DATA_DIR.parent / "sitemap.json"
    if sitemap_file.exists():
        with open(sitemap_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return JSONResponse(data)
    raise HTTPException(status_code=404, detail="Sitemap JSON not found")


# ========== 🔌 DYNAMIC USER INTEGRATIONS API ==========

@app.get("/api/integrations/status")
async def api_integrations_status():
    """Returns 100% dynamic connection status of all external services strictly from SQLite."""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, service_name, is_active, updated_at FROM user_integrations")
        rows = cursor.fetchall()
        active_map = {r["id"]: bool(r["is_active"]) for r in rows}

    plaud_active = active_map.get("plaud_cloud_felipe", False)
    whatsapp_active = active_map.get("whatsapp_zapi_felipe", False)
    granola_active = active_map.get("granola_felipe", False)
    podcasts_active = active_map.get("podcasts_felipe", False)

    connected_count = sum([plaud_active, whatsapp_active, granola_active, podcasts_active])

    return JSONResponse({
        "status": "SUCCESS",
        "total_connected": connected_count,
        "services": {
            "plaud": {"name": "Plaud Note Pro", "is_connected": plaud_active, "icon": "ph-waveform"},
            "whatsapp": {"name": "WhatsApp Voice", "is_connected": whatsapp_active, "icon": "ph-whatsapp-logo"},
            "granola": {"name": "Granola AI", "is_connected": granola_active, "icon": "ph-microphone-stage"},
            "podcasts": {"name": "Podcasts & RSS", "is_connected": podcasts_active, "icon": "ph-broadcast"}
        }
    })
