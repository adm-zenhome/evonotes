# Contexto compartilhado (Back + Front) — 2026-11-13

## Situacao
- Repo unico: adm-zenhome/evonotes (monorepo). Back = raiz Python. Front = dashboard/.
- Fronteira: dashboard/schemas.py + docs/contrato-api/openapi.yaml.
- Front pede endpoint em docs/PEDIDOS-AO-BACK.md; Back atende e atualiza openapi.yaml + CHANGELOG-API.md.
- Prompts: AGENTS.md (back) e dashboard/AGENTS.md (front). Releia ao iniciar conversa nova.
- PRs #1 e #2 ja na main. PR #3 (CI, template, parar de versionar .db) aberto: NAO fazer merge sem Volume no Railway.

## Riscos conhecidos
- Repo publico com .db e perfis no historico (exposicao). Decisao do Felipe: privado + filter-repo + rotacionar chaves.
- Sem CI de testes real e sem migracoes versionadas. Preview por PR depende de PR Environments no Railway.
- Rotas HTTP hoje vivem em dashboard/app.py; novas rotas do Painel ADM devem nascer em api/ (raiz) e ser montadas no app.

## Proximos passos
1. Back: atender PEDIDOS-AO-BACK.md do mais simples ao mais complexo, 1 PR por endpoint/grupo.
2. Front: implementar telas pela ordem do INVENTARIO-TELAS.md, mobile-first 390px.
3. Ambos: PR pequeno, resumo de 5 linhas, aguardar aprovacao do Felipe pelo celular.
