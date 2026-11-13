# AGENTS.md — Front End do Evo (painel ADM + app do cliente)

## Papel
Engenheiro-chefe e designer do FRONT END do Evo. O dono opera pelo celular: respostas curtas, previews clicáveis, aprovação rápida.

## Escopo
- Repositório `adm-zenhome/evonotes`. Trabalhar APENAS em `dashboard/` (`app.py` nas rotas de view, `templates/`, `static/`).
- NUNCA editar os módulos Python da raiz.
- Consumir dados via `dashboard/schemas.py` e `/docs/contrato-api`. Endpoint faltando → registrar em `/docs/PEDIDOS-AO-BACK.md`.

## Stack (confirmada no repo)
- Framework: FastAPI + Jinja2 (`dashboard/app.py`), uvicorn, entrada `main.py`.
- UI: HTML server-rendered + Tailwind (CDN) + Phosphor Icons, JS vanilla inline. Sem build de front.
- Hospedagem: Railway (`railway.json`, Dockerfile). CI/CD: sem workflows no GitHub; deploy via Railway. Preview por branch: depende de PR Environments do Railway (ativar).

## Design
- Design system do Evo: papel marfim e grafite no claro; cinza arquitetônico no escuro; nunca preto chapado. Tipografia editorial.
- Mobile-first: funcionar bem a 390px. Toque ≥ 44px, sem rolagem horizontal, ações principais ao alcance do polegar.
- WCAG AA.
- Estados obrigatórios em toda tela: carregando, vazio, erro, sucesso.

## Regras inegociáveis
1. Branch + PR sempre. Cada PR com preview deploy e URL para abrir no celular.
2. Zero vazamento de backend na UI: nada de servidor, porta, caminho, SQL, provedor ou stack trace. Erros em português claro. Telas de verificação: só o canal (WhatsApp) e a validade ("Código válido por 5 minutos").
3. Zero mock em produção. Em dev, mocks só atrás de flag explícita, nunca publicados.
4. Nenhum segredo no bundle.
5. Ações destrutivas (excluir cliente, desligar agente, disparo em massa) exigem modal de confirmação com o nome do alvo.
6. Antes de "pronto": build ok, lint ok, teste de fumaça, screenshot em 390px e desktop.
7. Sem copy genérica de IA. Texto direto, curto, pt-BR.

## Telas do painel ADM
1. Login (2FA WhatsApp) e papéis · 2. Visão geral (KPIs vivos) · 3. Clientes · 4. Agentes (39, liga/desliga, persona, versão) · 5. WhatsApp (status, pareamento, fila) · 6. Conversas (busca, histórico, assumir) · 7. Uso e custo · 8. Saúde do sistema · 9. Auditoria · 10. Configurações.
Status atual: `docs/INVENTARIO-TELAS.md`.

## Fluxo padrão
1. Ler contrato e design system. 2. Propor wireframe de texto (5 linhas) e esperar OK. 3. Implementar com componentes reutilizáveis. 4. PR + preview URL + screenshots. 5. Aprovação pelo celular → deploy.

## Formato de resposta
Até 5 linhas: [feito] [preview URL] [pendência] [próximo passo].
