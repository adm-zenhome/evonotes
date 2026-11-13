"""Ponto de entrada ASGI: app do dashboard + rotas do Painel ADM (api/)."""
from api import register_error_handlers
from api import router as admin_router
from dashboard.app import app

if not getattr(app.state, "admin_api_mounted", False):
    register_error_handlers(app)
    app.include_router(admin_router)
    app.state.admin_api_mounted = True
