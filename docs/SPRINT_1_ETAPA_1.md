# Nexyra CRM — Sprint 1 / Etapa 1

## Objetivo

Criar a fundação independente do Nexyra CRM.

## Entregas

- Estrutura inicial do projeto
- API FastAPI
- Configuração central
- Endpoint raiz
- Health check
- Testes automatizados
- Ruff
- Dependências preparadas para banco de dados e migrations

## Critérios de aprovação

A etapa é aprovada quando:

1. `pytest -q` passa sem falhas.
2. `ruff check app tests` passa sem erros.
3. A API inicia na porta 5060.
4. `/` responde com `ok: true`.
5. `/api/v1/health` responde com produto, versão e ambiente.

## Próxima etapa

Sprint 1 / Etapa 2:

- SQLAlchemy
- banco SQLite de desenvolvimento
- preparação para PostgreSQL
- Alembic
- primeira migration
- base para arquitetura multiempresa
