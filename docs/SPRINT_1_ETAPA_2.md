# Nexyra CRM — Sprint 1 / Etapa 2

## Objetivo

Criar a fundação real de persistência do Nexyra CRM.

## Entregas

- SQLAlchemy 2.x
- Base declarativa
- Engine e SessionLocal
- Dependency `get_db`
- Configuração para SQLite em desenvolvimento
- Estrutura pronta para PostgreSQL
- Alembic configurado
- Primeira migration
- Tabela base `workspaces`
- Testes de persistência
- Restrição de unicidade de workspace

## Arquitetura

O Nexyra CRM continua independente do Atlas.

O banco pertence ao Nexyra CRM. O Atlas futuramente acessará os dados somente por contratos de integração/API, respeitando permissões e auditoria.

## Comandos de validação

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check app tests alembic
```

## Inspeção da migration

```powershell
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic heads
```

Esperado:

`0001_create_workspaces`

## Próxima etapa

Sprint 1 / Etapa 3 — Workspaces multiempresa:

- schemas Pydantic
- repository
- service
- CRUD de empresas/workspaces
- validação de slug
- isolamento de tenant
- endpoints REST
- testes de API
