# 🗺️ Executive Voice OS — Sitemap Oficial & Índice de Rotas (SSOT)

> **Versão:** 4.2.0 • **Última Atualização:** 29/08/2026 12:30  
> **Propósito:** Fonte Única da Verdade (SSOT) para navegação, governança de agentes Jarvis/Antigravity e indexação SEO.

---

## 🏛️ 1. Páginas, Telas & Modais da Aplicação

| Rota / Âncora | Nome da Tela | Tipo | Prioridade | Propósito / Funcionalidades |
| :--- | :--- | :--- | :--- | :--- |
| [`/app`](file:///Users/felipe/Jarvis/modules/executive_voice_os/dashboard/templates/index.html) | **Painel Principal & Canvas** | Aplicação / Core | `1.0` | Dashboard Bifocal (Horas economizadas, Pipeline ativo, Player MEMS+VCS, Chat Copiloto Spark). |
| [`/app#login`](file:///Users/felipe/Jarvis/modules/executive_voice_os/dashboard/templates/index.html) | **Acesso Executivo Premium** | Segurança / Gate | `0.9` | Gate de governança Guardian Auth v4 com Fast-Pass para Felipe Donato e criptografia ativa. |
| [`/app#tasks`](file:///Users/felipe/Jarvis/modules/executive_voice_os/dashboard/templates/index.html) | **Central de Tarefas** | Aplicação / View | `0.9` | Gestão de compromissos com gestos de deslizar (Swipe-to-Action) no iPhone e Google Calendar 1-Click. |
| [`/app#whatsapp-inbox`](file:///Users/felipe/Jarvis/modules/executive_voice_os/dashboard/templates/index.html) | **Triagem de Áudios WhatsApp** | Aplicação / Modal | `0.85` | Fila real de mensagens de voz recebidas em grupos e chats via Z-API. Criação mediante confirmação explícita. |
| [`/app#settings`](file:///Users/felipe/Jarvis/modules/executive_voice_os/dashboard/templates/index.html) | **Hub de Conexões** | Aplicação / Modal | `0.8` | Gerenciamento de credenciais e status de Plaud Note Pro, WhatsApp Z-API, Gmail e Google Calendar. |
| [`/app#vocab`](file:///Users/felipe/Jarvis/modules/executive_voice_os/dashboard/templates/index.html) | **Nuvem de Vocabulário** | IA / Calibração | `0.8` | Nuvem viva de termos e jargões extraídos das reuniões para aprovação/descarte (👍/👎). |
| [`/app#categories`](file:///Users/felipe/Jarvis/modules/executive_voice_os/dashboard/templates/index.html) | **Gestão de Categorias** | Governança | `0.75` | Criação e personalização de categorias com ícones Phosphor. |
| [`/app#stakeholders`](file:///Users/felipe/Jarvis/modules/executive_voice_os/dashboard/templates/index.html) | **Diretório de Stakeholders** | Inteligência 360° | `0.85` | Dossiês 360° com perfil de comunicação, histórico de falas e compromissos por pessoa. |

---

## 🎨 2. Templates Polimórficos de Inteligência

| Template | Rota / Contexto | Foco Estratégico | Abas e Seções Entregues |
| :--- | :--- | :--- | :--- |
| **🏢 Comercial B2B** | `/app?template=b2b_sales` | Receita, Margem, Deals | Síntese C-Level, Objeções MEDDPICC, Contas & Oportunidades, Rascunho de E-mail de Follow-up. |
| **🌿 Pessoal & Família** | `/app?template=personal_family` | Família, Saúde, Rotina | Diário & Memória Afetiva, Momentos Marcantes, Lembretes & Tarefas Domésticas. |
| **🧠 Mentoria & Aprendizado** | `/app?template=mentorship_learning` | Modelos Mentais, Hábitos | Teses Centrais, Modelos Mentais, Frases de Impacto, Hábitos & Práticas Recomendadas. |
| **🚀 Ideias & Produto** | `/app?template=product_brainstorm` | Inovação, Roadmap | Problema vs Solução, Decisões de Arquitetura, Riscos Técnicos, Próximos Passos de Roadmap. |
| **🤝 1-on-1 & Liderança** | `/app?template=one_on_one` | Pessoas, Metas, Feedback | Pauta & Clima, Feedbacks Mútuos, Metas de Carreira, Plano de Ação Conjunto. |
| **⚡ Nota Rápida** | `/app?template=quick_note` | Agilidade no Trânsito | Ideia Central (3 linhas), Ação Imediata (1-Click). |

---

## ⚡ 3. Endpoints da API REST & Integrações

- `POST /api/sync-plaud` — Sincronização do hardware Plaud Note Pro.
- `GET /api/meetings` — Listagem de todas as reuniões persistidas no SQLite.
- `GET /api/meetings/<id>` — Detalhes completos de inteligência da nota.
- `POST /api/meetings/<id>/reprocess-template` — Re-análise adaptativa sob novo template.
- `GET /api/tasks` — Central de tarefas e ações executivas.
- `POST /api/tasks/<id>/status` — Atualização de status de tarefa (`pending`, `completed`, `deferred`).
- `GET /api/whatsapp/audio-feed` — Fila de triagem de áudios reais do WhatsApp.
- `POST /api/whatsapp/ingest-audio-item` — Ingestão confirmada de áudio do WhatsApp.
- `POST /api/webhook/whatsapp` — Webhook de recepção de áudios em tempo real via Z-API.
- `POST /api/ai-action/<file_id>` — Perguntas contextuais ao Copiloto Spark sobre uma nota.
- `POST /api/ai-action/global` — Consultas executivas cross-meeting ao Copiloto Spark.
- `POST /api/generate-audio-briefing/<id>` — Direção de áudio vocal com síntese ElevenLabs.
- `POST /api/meetings/<id>/export-obsidian` — Exportação de notas para o Obsidian Vault.
- `GET /sitemap.xml` — Sitemap XML padrão para indexadores e SEO.
- `GET /sitemap.json` — Sitemap estruturado em JSON para agentes e automações.
- `GET /api/sitemap` — API REST para consulta do sitemap do sistema.
