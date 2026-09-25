# Nexyra CRM — Sprint 2 / Etapa 4

## Pipeline Kanban + Oportunidades

Esta etapa transforma os módulos `Pipeline` e `Oportunidades` em telas funcionais conectadas ao backend real do Nexyra CRM.

### Backend

Novos endpoints:

- `GET /api/v1/workspaces/{workspace}/pipeline/board`
- `GET /api/v1/workspaces/{workspace}/opportunities/search`

O board retorna somente oportunidades abertas, agrupadas pelas etapas configuradas no workspace.

Filtros suportados:

- busca textual
- responsável
- sem responsável
- etapa
- status
- paginação na listagem de oportunidades

Nenhuma migration nova é necessária.

### Frontend

#### Pipeline

- Kanban profissional
- colunas baseadas no pipeline configurável do segmento
- drag and drop entre etapas
- valor total por coluna
- quantidade por coluna
- valor total do pipeline
- ticket médio aberto
- busca
- filtro por responsável
- cadastro de oportunidade
- edição
- marcar como ganha
- marcar como perdida
- histórico de movimentações em drawer lateral

#### Oportunidades

- tabela profissional
- busca
- filtros por status, etapa e responsável
- paginação
- cadastro
- edição
- detalhes
- histórico
- ganho/perda

### Segurança e auditoria

As movimentações continuam usando os serviços oficiais da Sprint 1. Portanto, alterações de oportunidade permanecem registradas na auditoria existente.

A autenticação real de usuário ainda é uma etapa futura. Até lá, ações sem identidade autenticada continuam auditadas como `system`, conforme a arquitetura já definida.

### Validação

No ambiente de montagem desta etapa:

- `pytest`: 77 testes passaram
- `compileall`: passou
- migrations: nenhuma nova migration
- TS/TSX: arquivos analisados sem erro de parsing

O Ruff não estava instalado no ambiente de montagem. Rode o Ruff no `.venv` oficial do projeto.
