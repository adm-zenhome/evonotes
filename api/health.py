"""GET /api/admin/health — status com nomes públicos, sem host/porta/provedor."""
import os
import sqlite3

from fastapi import APIRouter

router = APIRouter(tags=["saude"])

# nome_publico -> variável de ambiente que indica configuração (nunca exposta)
_INTEGRATIONS = {
    "Inteligência artificial": "OPENAI_API_KEY",
    "Voz": "ELEVENLABS_API_KEY",
    "E-mail": "RESEND_API_KEY",
}


def _check_db() -> str:
    try:
        from database import DB_PATH

        conn = sqlite3.connect(DB_PATH, timeout=2.0)
        try:
            conn.execute("SELECT 1").fetchone()
        finally:
            conn.close()
        return "ok"
    except (sqlite3.Error, ImportError, OSError):
        return "fora"


def build_health() -> dict:
    componentes = [{"nome_publico": "Banco de dados", "status": _check_db()}]
    for nome, env in _INTEGRATIONS.items():
        componentes.append(
            {"nome_publico": nome, "status": "ok" if os.environ.get(env) else "nao_configurado"}
        )
    if componentes[0]["status"] == "fora":
        status = "fora"
    elif any(c["status"] != "ok" for c in componentes):
        status = "degradado"
    else:
        status = "ok"
    return {"status": status, "componentes": componentes}


@router.get("/health")
def admin_health():
    return build_health()
