# Pedidos ao Back

Erros sempre como `{ "code": "...", "message": "<pt-BR humano>" }`, sem `str(e)` nem stack trace.

## Auth e papéis
- `POST /api/admin/auth/otp/send` `{phone}` → `{expires_in: 300}`
- `POST /api/admin/auth/otp/verify` `{phone, code}` → cookie de sessão HttpOnly
- `GET /api/admin/me` → `{id, nome, papel: "owner"|"admin"|"suporte"|"leitura"}`
- `POST /api/admin/auth/logout`

## Visão geral
- `GET /api/admin/overview` → `{contas_ativas, mensagens_24h, custo_mes_brl, alertas_abertos, atualizado_em}` (+ SSE `/api/admin/overview/stream` opcional)

## Clientes
- `GET /api/admin/clients?q=&status=&page=` · `GET /api/admin/clients/{id}`
- `PATCH /api/admin/clients/{id}/plan` `{plano}`
- `POST /api/admin/clients/{id}/suspend` / `reactivate` · `DELETE /api/admin/clients/{id}`

## Agentes
- `GET /api/admin/agents` → `[{id, nome, persona, versao, ativo, ultima_execucao}]` (39)
- `PATCH /api/admin/agents/{id}` `{ativo?, persona?}` · `GET /api/admin/agents/{id}/versions`

## WhatsApp
- Reaproveitar `status`, `qr-code`, `connect`, `disconnect` (padronizar erro, sem nome de provedor)
- `GET /api/admin/whatsapp/queue` → `[{id, destino, status, tentativas, criado_em}]`
- `POST /api/admin/whatsapp/broadcast` `{segmento, texto}` (+ `dry_run` com contagem)

## Conversas
- `GET /api/admin/conversations?q=&client_id=` · `GET /api/admin/conversations/{id}/messages`
- `POST /api/admin/conversations/{id}/takeover` / `release` · `POST .../messages` `{texto}`

## Uso e custo
- `GET /api/admin/usage?de=&ate=&agrupar=dia|cliente|agente` · `GET/PUT /api/admin/quotas` · `GET /api/admin/alerts`

## Saúde
- `GET /api/admin/health` → `{status, componentes:[{nome_publico, status}]}` (nomes públicos, sem host/porta)
- `GET /api/admin/errors?page=` (mensagem resumida, sem trace) · `GET /api/admin/jobs`

## Auditoria
- `GET /api/admin/audit?ator=&acao=&alvo=&de=&ate=&cursor=`

## Configurações
- `GET/PATCH /api/admin/settings`

## Contrato
- Publicar `/docs/contrato-api` (OpenAPI do FastAPI já serve de base) e mover modelos para `dashboard/schemas.py`.
