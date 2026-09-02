#!/usr/bin/env python3
"""
EvoNotes Model Context Protocol (MCP) Server
Allows external AI clients (ChatGPT Desktop, Claude Desktop, Cursor, Antigravity, Copilot)
to query, search, create, and update notes, action items, and executive intelligence.

Protocol: Model Context Protocol (JSON-RPC 2.0 over Stdio)
"""

import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

# Ensure sandbox directory is in sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from database import db
from intelligence_engine import IntelligenceEngine

# Configure logging strictly to stderr so stdout remains 100% clean for JSON-RPC
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [EvoNotes-MCP] %(levelname)s: %(message)s"
)
logger = logging.getLogger("EvoNotesMCP")

SERVER_NAME = "evonotes"
SERVER_VERSION = "1.0.0"

# =========================================================================
# 🛠️ MCP TOOL SCHEMAS
# =========================================================================

MCP_TOOLS = [
    {
        "name": "search_notes",
        "description": "Busca notas, reuniões e transcrições de voz no EvoNotes por palavra-chave, cliente, projeto ou categoria.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Termo de busca (ex: 'Zendesk', 'BCR', 'contrato', 'anamnese', 'orçamento')"
                },
                "limit": {
                    "type": "integer",
                    "description": "Número máximo de notas a retornar (padrão: 5)",
                    "default": 5
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_recent_notes",
        "description": "Obtém as notas e reuniões executivas mais recentes salvas no EvoNotes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Quantidade de notas mais recentes (padrão: 5)",
                    "default": 5
                },
                "category": {
                    "type": "string",
                    "description": "Filtrar por categoria específica (opcional, ex: 'Comercial', 'Geral', 'WhatsApp')"
                }
            }
        }
    },
    {
        "name": "get_note_details",
        "description": "Obtém todos os detalhes estruturados de uma nota (síntese executiva, decisões, participantes, tarefas e transcrição completa).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_id": {
                    "type": "string",
                    "description": "O ID da nota ou reunião (ex: 'wa_123', 'rec_456')"
                }
            },
            "required": ["file_id"]
        }
    },
    {
        "name": "get_tasks",
        "description": "Consulta a Central de Tarefas e Ações Executivas do EvoNotes, filtrando por status e responsável.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["PENDING", "DONE", "ALL"],
                    "description": "Status das tarefas: 'PENDING' (apenas pendentes), 'DONE' (concluídas) ou 'ALL' (todas)",
                    "default": "PENDING"
                },
                "owner": {
                    "type": "string",
                    "description": "Filtrar por responsável (ex: 'Você', 'Felipe', ou deixar vazio para todas)"
                }
            }
        }
    },
    {
        "name": "create_task",
        "description": "Adiciona uma nova tarefa ou compromisso diretamente na Central de Tarefas do EvoNotes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Ação ou compromisso a ser executado (ex: 'Revisar proposta comercial e enviar minuta')"
                },
                "owner": {
                    "type": "string",
                    "description": "Responsável pela tarefa (padrão: 'Você')",
                    "default": "Você"
                },
                "deadline": {
                    "type": "string",
                    "description": "Prazo da tarefa (ex: 'Hoje', 'Amanhã', '2026-09-05')",
                    "default": "Hoje"
                },
                "meeting_id": {
                    "type": "string",
                    "description": "ID da nota de origem associada (opcional)",
                    "default": "general"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "complete_task",
        "description": "Marca uma tarefa existente como concluída no EvoNotes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "integer",
                    "description": "ID numérico da tarefa no EvoNotes"
                }
            },
            "required": ["task_id"]
        }
    },
    {
        "name": "create_note",
        "description": "Cria uma nova nota executiva estruturada diretamente no EvoNotes a partir de texto ou decisões tomadas no ChatGPT/Claude.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Título claro da nota ou decisão"
                },
                "content": {
                    "type": "string",
                    "description": "Conteúdo, deliberações ou síntese da reunião/conversa"
                },
                "category": {
                    "type": "string",
                    "description": "Categoria da nota (ex: 'Geral', 'Comercial', 'Tecnologia')",
                    "default": "Geral"
                },
                "tasks": {
                    "type": "array",
                    "description": "Lista opcional de tarefas extraídas da nota",
                    "items": {
                        "type": "object",
                        "properties": {
                            "action": {"type": "string"},
                            "owner": {"type": "string", "default": "Você"},
                            "deadline": {"type": "string", "default": "Hoje"}
                        },
                        "required": ["action"]
                    }
                }
            },
            "required": ["title", "content"]
        }
    },
    {
        "name": "get_executive_briefing",
        "description": "Gera um briefing executivo consolidado com as principais decisões, horas economizadas e pendências críticas recentes no EvoNotes.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]

# =========================================================================
# ⚙️ TOOL IMPLEMENTATIONS
# =========================================================================

def execute_search_notes(arguments: Dict[str, Any]) -> str:
    query = arguments.get("query", "").strip().lower()
    limit = int(arguments.get("limit", 5))
    
    meetings = db.get_all_meetings()
    matches = []
    
    for m in meetings:
        title = (m.get("title") or "").lower()
        summary = (m.get("executive_summary") or "").lower()
        transcript = (m.get("transcript_full") or "").lower()
        category = (m.get("category") or "").lower()
        
        if query in title or query in summary or query in transcript or query in category:
            matches.append({
                "file_id": m.get("file_id"),
                "title": m.get("title"),
                "category": m.get("category"),
                "start_time": m.get("start_time"),
                "summary_excerpt": (m.get("executive_summary") or "")[:200] + "..." if len(m.get("executive_summary") or "") > 200 else m.get("executive_summary")
            })
            if len(matches) >= limit:
                break
                
    if not matches:
        return f"Nenhuma nota encontrada para o termo '{query}' no EvoNotes."
        
    res = f"🔍 **Resultados encontrados no EvoNotes ({len(matches)}):**\n\n"
    for idx, item in enumerate(matches, 1):
        res += f"**{idx}. {item['title']}** (ID: `{item['file_id']}`)\n"
        res += f"   - *Categoria:* {item['category']} | *Data:* {item['start_time']}\n"
        res += f"   - *Síntese:* {item['summary_excerpt']}\n\n"
    return res

def execute_get_recent_notes(arguments: Dict[str, Any]) -> str:
    category_filter = arguments.get("category")
    sort_by = arguments.get("sort_by", "").lower()
    
    meetings = db.get_all_meetings()
    if category_filter:
        meetings = [m for m in meetings if (m.get("category") or "").lower() == category_filter.lower()]
        
    if not meetings:
        return "📋 Nenhuma nota encontrada no seu workspace do EvoNotes."
        
    if "cliente" in sort_by or "empresa" in sort_by:
        grouped = {}
        for m in meetings:
            t = m.get("title") or ""
            c = "Outros / Geral"
            if "Britânia" in t: c = "🏢 Britânia"
            elif "Wine" in t: c = "🍷 Wine"
            elif "Augusto Cury" in t or "Cury" in t: c = "🧠 Desenvolvimento / Cury"
            elif "WhatsApp" in t: c = "📱 WhatsApp Oficial"
            grouped.setdefault(c, []).append(m)
        
        lines = [f"📂 *Todas as suas Notas ({len(meetings)} no total) Organizadas por Cliente/Conta:*\n"]
        for grp_name, m_list in grouped.items():
            lines.append(f"*{grp_name}* ({len(m_list)} registros)")
            for idx, m in enumerate(m_list, 1):
                m_date = (m.get("start_time") or "")[:10]
                m_title = (m.get("title") or "").replace("🎙️", "").strip()
                m_dur = round((m.get("duration_seconds") or 0) / 60, 1)
                lines.append(f"• *{m_title}* — _{m_date}_ ({m_dur} min)")
            lines.append("")
        return "\n".join(lines).strip()

    # Default list of all notes
    lines = [f"📋 *Todas as suas Notas Registradas no EvoNotes ({len(meetings)} no total):*\n"]
    for idx, m in enumerate(meetings, 1):
        m_date = (m.get("start_time") or "")[:10]
        m_title = (m.get("title") or "").replace("🎙️", "").strip()
        m_dur = round((m.get("duration_seconds") or 0) / 60, 1)
        m_cat = m.get("category") or "Geral"
        m_sum = (m.get("executive_summary") or "")[:120]
        lines.append(f"*{idx}. {m_title}*")
        lines.append(f"   • _Data:_ {m_date} | _Duração:_ {m_dur} min | _Categoria:_ {m_cat}")
        if m_sum:
            lines.append(f"   • _Síntese:_ {m_sum}...")
        lines.append("")
        
    lines.append("💡 *Personalização de Visualização:*")
    lines.append("_Chefe, deseja que eu reordene esta lista por: 1. Data mais recente, 2. Cliente / Empresa (Britânia, Wine, etc.), ou 3. Categoria?_")
    return "\n".join(lines).strip()

def execute_get_note_details(arguments: Dict[str, Any]) -> str:
    file_id = arguments.get("file_id")
    meeting = db.get_meeting(file_id)
    if not meeting:
        return f"Nota com ID `{file_id}` não foi encontrada no EvoNotes."
        
    intel = meeting.get("intelligence") or {}
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM commitments WHERE meeting_id = ?", (file_id,))
        tasks = [dict(r) for r in cursor.fetchall()]
    
    res = f"# 📄 {meeting.get('title')}\n\n"
    res += f"- **ID:** `{file_id}`\n"
    res += f"- **Categoria:** {meeting.get('category') or 'Geral'}\n"
    res += f"- **Data:** {meeting.get('start_time') or 'Hoje'}\n"
    res += f"- **Duração:** {(meeting.get('duration_seconds') or 0) // 60} min\n\n"
    
    res += f"## 🎯 Síntese Executiva:\n{meeting.get('executive_summary') or 'Sem resumo.'}\n\n"
    
    highlights = intel.get("key_highlights") or []
    if highlights:
        res += "## 💡 Destaques & Decisões:\n"
        for h in highlights:
            res += f"- {h}\n"
        res += "\n"
        
    if tasks:
        res += "## ✅ Tarefas & Compromissos:\n"
        for t in tasks:
            status_icon = "✅" if t.get("status") == "DONE" else "⏳"
            res += f"- {status_icon} **[{t.get('owner', 'Você')}]:** {t.get('action')} (Prazo: {t.get('deadline_or_context', 'Hoje')})\n"
        res += "\n"
        
    transcript = meeting.get("transcript_full") or ""
    if transcript:
        res += f"## 📝 Transcrição Original:\n{transcript[:1500]}"
        if len(transcript) > 1500:
            res += "\n\n*(Transcrição truncada para exibição resumida)*"
            
    return res

def execute_get_tasks(arguments: Dict[str, Any]) -> str:
    status = arguments.get("status", "PENDING")
    owner_filter = arguments.get("owner", "").lower().strip()
    
    tasks = db.get_all_tasks(status=status if status != "ALL" else None)
        
    if owner_filter:
        tasks = [t for t in tasks if owner_filter in (t.get("owner") or "").lower()]
        
    if not tasks:
        return f"Nenhuma tarefa encontrada com o status '{status}'."
        
    res = f"📋 **Central de Tarefas EvoNotes ({len(tasks)} itens):**\n\n"
    for t in tasks:
        status_icon = "✅ [Concluída]" if t.get("status") == "DONE" else "⏳ [Pendente]"
        res += f"- **ID #{t.get('id')}:** {status_icon} **{t.get('action')}**\n"
        res += f"   - *Responsável:* {t.get('owner', 'Você')} | *Prazo:* {t.get('deadline_or_context', 'Hoje')}\n"
        if t.get("meeting_title"):
            res += f"   - *Origem:* {t.get('meeting_title')}\n"
        res += "\n"
    return res

def execute_create_task(arguments: Dict[str, Any]) -> str:
    action = arguments.get("action")
    owner = arguments.get("owner", "Você")
    deadline = arguments.get("deadline", "Hoje")
    meeting_id = arguments.get("meeting_id", "general")
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO commitments (meeting_id, owner, action, deadline_or_context, status, created_at)
            VALUES (?, ?, ?, ?, 'PENDING', CURRENT_TIMESTAMP)
        """, (meeting_id, owner, action, deadline))
        task_id = cursor.lastrowid
        conn.commit()
        
    return f"✅ **Tarefa criada com sucesso no EvoNotes!**\n- **ID:** #{task_id}\n- **Ação:** {action}\n- **Responsável:** {owner}\n- **Prazo:** {deadline}"

def execute_complete_task(arguments: Dict[str, Any]) -> str:
    task_id = arguments.get("task_id")
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE commitments SET status = 'DONE', completed_at = CURRENT_TIMESTAMP WHERE id = ?", (task_id,))
        rows = cursor.rowcount
        conn.commit()
        
    if rows > 0:
        return f"✅ Tarefa #{task_id} marcada como CONCLUÍDA no EvoNotes!"
    else:
        return f"❌ Tarefa com ID #{task_id} não foi encontrada no banco."

def execute_create_note(arguments: Dict[str, Any]) -> str:
    title = arguments.get("title")
    content = arguments.get("content")
    category = arguments.get("category", "Geral")
    tasks_to_create = arguments.get("tasks", [])
    
    file_id = f"mcp_{int(datetime.now().timestamp())}"
    
    intel = {
        "meeting_title": title,
        "executive_summary": content,
        "category": category,
        "key_highlights": [content[:100]],
        "commitments_and_promises": tasks_to_create
    }
    
    db.save_meeting({
        "file_id": file_id,
        "title": title,
        "category": category,
        "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "duration_seconds": 120,
        "executive_summary": content,
        "intelligence": intel,
        "transcript_full": content,
        "custom_notes": "Criada via integração MCP externa (ChatGPT / Claude)"
    })
    
    return f"🚀 **Nota criada com sucesso no EvoNotes!**\n- **ID:** `{file_id}`\n- **Título:** {title}\n- **Categoria:** {category}\n- **Tarefas vinculadas:** {len(tasks_to_create)}"

def execute_get_executive_briefing(arguments: Dict[str, Any]) -> str:
    meetings = db.get_all_meetings()
    tasks = db.get_all_tasks(status="ALL")
    pending_tasks = [t for t in tasks if t.get("status") == "PENDING"]
    
    hours_saved = round(max(0.8, len(meetings) * 0.4), 1)
    
    res = f"# 🏛️ EvoNotes Executive Briefing\n\n"
    res += f"📊 **Métricas da Base:**\n"
    res += f"- **Notas Processadas:** {len(meetings)}\n"
    res += f"- **Tempo Economizado:** {hours_saved}h\n"
    res += f"- **Tarefas Pendentes Ativas:** {len(pending_tasks)}\n\n"
    
    res += f"### 📌 Últimas 3 Notas Registradas:\n"
    for m in meetings[:3]:
        res += f"- **{m.get('title')}:** {(m.get('executive_summary') or '')[:120]}...\n"
    res += "\n"
    
    res += f"### ⚡ Top 3 Tarefas Imediatas:\n"
    for t in pending_tasks[:3]:
        res += f"- **[{t.get('owner', 'Você')}]:** {t.get('action')} (Prazo: {t.get('deadline_or_context', 'Hoje')})\n"
        
    return res

# Tool Dispatch Table
TOOL_HANDLERS = {
    "search_notes": execute_search_notes,
    "get_recent_notes": execute_get_recent_notes,
    "get_note_details": execute_get_note_details,
    "get_tasks": execute_get_tasks,
    "create_task": execute_create_task,
    "complete_task": execute_complete_task,
    "create_note": execute_create_note,
    "get_executive_briefing": execute_get_executive_briefing
}

# =========================================================================
# 🔄 JSON-RPC 2.0 PROTOCOL ENGINE
# =========================================================================

def handle_json_rpc(message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    msg_id = message.get("id")
    method = message.get("method")
    params = message.get("params", {})

    logger.info(f"Received method: {method} (id={msg_id})")

    # 1. Initialize
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": False},
                    "resources": {"subscribe": False, "listChanged": False}
                },
                "serverInfo": {
                    "name": SERVER_NAME,
                    "version": SERVER_VERSION
                }
            }
        }

    # 2. Initialized notification
    if method == "notifications/initialized":
        logger.info("Client successfully initialized MCP session.")
        return None

    # 3. Ping
    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

    # 4. Tools List
    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "tools": MCP_TOOLS
            }
        }

    # 5. Tools Call
    if method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        handler = TOOL_HANDLERS.get(tool_name)
        if not handler:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32601,
                    "message": f"Tool '{tool_name}' not found on EvoNotes MCP Server."
                }
            }
            
        try:
            result_text = handler(arguments)
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": result_text
                        }
                    ],
                    "isError": False
                }
            }
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Erro ao executar {tool_name}: {str(e)}"
                        }
                    ],
                    "isError": True
                }
            }

    # 6. Resources List
    if method == "resources/list":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "resources": [
                    {
                        "uri": "evonotes://recent-notes",
                        "name": "Notas Recentes",
                        "description": "Lista das últimas notas registradas no EvoNotes",
                        "mimeType": "application/json"
                    },
                    {
                        "uri": "evonotes://pending-tasks",
                        "name": "Tarefas Pendentes",
                        "description": "Lista de to-dos e compromissos ativos",
                        "mimeType": "application/json"
                    }
                ]
            }
        }

    # 7. Resources Read
    if method == "resources/read":
        uri = params.get("uri", "")
        if uri == "evonotes://recent-notes":
            meetings = db.get_all_meetings()[:10]
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "contents": [
                        {
                            "uri": uri,
                            "mimeType": "application/json",
                            "text": json.dumps(meetings, ensure_ascii=False, indent=2)
                        }
                    ]
                }
            }
        elif uri == "evonotes://pending-tasks":
            tasks = [t for t in db.get_all_tasks(status="PENDING")]
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "contents": [
                        {
                            "uri": uri,
                            "mimeType": "application/json",
                            "text": json.dumps(tasks, ensure_ascii=False, indent=2)
                        }
                    ]
                }
            }
        else:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32602,
                    "message": f"Resource URI '{uri}' not found."
                }
            }

    # Unknown method
    if msg_id is not None:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {
                "code": -32601,
                "message": f"Method '{method}' not recognized by EvoNotes MCP Server."
            }
        }
    return None

# =========================================================================
# 🚀 MAIN LOOP (STDIO)
# =========================================================================

def main():
    logger.info("EvoNotes MCP Server started on stdio.")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
            response = handle_json_rpc(message)
            if response:
                sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
                sys.stdout.flush()
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON from stdin: {e}")
            err_resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": f"Parse error: {str(e)}"}}
            sys.stdout.write(json.dumps(err_resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}", exc_info=True)
            err_resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": f"Internal error: {str(e)}"}}
            sys.stdout.write(json.dumps(err_resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()

if __name__ == "__main__":
    main()
