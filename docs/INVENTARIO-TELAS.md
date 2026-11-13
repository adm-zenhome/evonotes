# Inventário de telas — Painel ADM

Hoje o `dashboard/` é o app do **cliente** (EvoNotes: reuniões, tarefas, briefings). Não existe painel ADM multi-conta.

| # | Tela | Status | O que existe |
|---|------|--------|--------------|
| 1 | Login 2FA WhatsApp + papéis | **Parcial** | `login.html` + `send-otp`/`verify-otp`. Sem sessão real nem papéis; `/dashboard` abre sem auth. |
| 2 | Visão geral (KPIs) | **Falta** | Só KPIs do cliente (`/api/analytics`). |
| 3 | Clientes | **Falta** | App é single-user (`felipe_donato` fixo em `app.py`). |
| 4 | Agentes (39) | **Falta** | Nenhum registro de agentes. |
| 5 | WhatsApp | **Parcial** | `status`, `qr-code`, `connect/disconnect`. Sem fila de envio. |
| 6 | Conversas | **Parcial** | `whatsapp/feed`, `audio-feed`. Sem busca/assumir. |
| 7 | Uso e custo | **Falta** | — |
| 8 | Saúde do sistema | **Parcial** | `/api/health`, `system/tasks-running`. Sem erros/jobs. |
| 9 | Auditoria | **Falta** | — |
| 10 | Configurações | **Parcial** | Perfil, preferências, canais, categorias (escopo cliente). |

## Problemas encontrados (front)
- `/dashboard` devolve **stack trace em HTML** no erro (viola regra 2). `str(e)` vaza em várias respostas JSON.
- `index.html` monolítico (11.6k linhas), sem componentes.
- Usuário fixo `felipe_donato` na view.
- Rota `/ogin` duplicada (typo tolerado).
- Sem CI, sem lint, sem preview por branch.
