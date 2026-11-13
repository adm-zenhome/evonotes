"""Painel ADM — rotas do back (raiz). Montadas no app via asgi.py, sem editar dashboard/."""
from fastapi import APIRouter

from api.errors import register_error_handlers  # noqa: F401
from api.health import router as health_router

router = APIRouter(prefix="/api/admin")
router.include_router(health_router)
