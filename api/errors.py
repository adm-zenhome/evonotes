"""Erros padronizados {code, message} em pt-BR, sem detalhes internos."""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

log = logging.getLogger("evo.api")
ADMIN_PREFIX = "/api/admin"

_MESSAGES = {
    400: ("requisicao_invalida", "Requisição inválida."),
    401: ("nao_autenticado", "Faça login para continuar."),
    403: ("sem_permissao", "Você não tem permissão para esta ação."),
    404: ("nao_encontrado", "Recurso não encontrado."),
    409: ("conflito", "A ação conflita com o estado atual."),
    422: ("dados_invalidos", "Alguns campos estão inválidos."),
    429: ("muitas_requisicoes", "Muitas tentativas. Aguarde e tente de novo."),
}


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


def error_body(status: int, code: str | None = None, message: str | None = None) -> dict:
    d_code, d_msg = _MESSAGES.get(status, ("erro_interno", "Erro inesperado. Tente novamente."))
    return {"code": code or d_code, "message": message or d_msg}


def register_error_handlers(app: FastAPI) -> None:
    """Só afeta rotas /api/admin; demais rotas mantêm o comportamento atual."""

    def _is_admin(request: Request) -> bool:
        return request.url.path.startswith(ADMIN_PREFIX)

    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError):
        return JSONResponse(error_body(exc.status, exc.code, exc.message), status_code=exc.status)

    prev_http = app.exception_handlers.get(HTTPException)
    prev_val = app.exception_handlers.get(RequestValidationError)

    @app.exception_handler(HTTPException)
    async def _http(request: Request, exc: HTTPException):
        if _is_admin(request) or prev_http is None:
            return JSONResponse(error_body(exc.status_code), status_code=exc.status_code)
        return await prev_http(request, exc)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        if _is_admin(request) or prev_val is None:
            return JSONResponse(error_body(422), status_code=422)
        return await prev_val(request, exc)

    @app.middleware("http")
    async def _unhandled(request: Request, call_next):
        try:
            return await call_next(request)
        except Exception:
            if not _is_admin(request):
                raise
            log.exception("admin api unhandled error")  # trace só no log do servidor
            return JSONResponse(error_body(500), status_code=500)
