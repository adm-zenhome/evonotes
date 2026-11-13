# CHANGELOG da API

## 0.2.0 — 2026-11-13
- NOVO `GET /api/admin/health` (público, sanitizado).
- Todas as rotas `/api/admin/*` retornam erro como `{code, message}` em pt-BR.
- Entrada do servidor passa a ser `asgi:app` (dashboard + `api/`).

## 0.1.0-draft — 2026-11-13
- Esqueleto `/v1` do Painel ADM em `docs/contrato-api/openapi.yaml` (não implementado).
