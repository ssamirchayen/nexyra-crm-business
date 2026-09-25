# Nexyra CRM — Sprint 2 / Etapa 3

## Tela profissional de Leads

Esta etapa transforma o módulo de Leads em uma área funcional ligada à API real do Nexyra CRM.

### Frontend

- tabela profissional de leads
- busca com debounce
- filtros por status, prioridade, origem, canal, campanha, responsável e ativo/inativo
- paginação
- cadastro manual
- edição
- desativação com confirmação
- drawer de detalhes
- campos dinâmicos conforme o segmento do workspace
- responsáveis carregados da equipe real do workspace
- registro via intake para origens externas
- feedback de erro, loading, vazio e sucesso

### Intake

O botão **Registrar entrada** utiliza:

`POST /api/v1/workspaces/{workspace_public_id}/leads/intake`

Se o lead já existir por telefone, e-mail ou `external_id`, o backend atualiza o registro existente e retorna `duplicate_updated`.

### Backend

Novo endpoint de consulta paginada:

`GET /api/v1/workspaces/{workspace_public_id}/leads/search`

Filtros suportados:

- `q`
- `lead_status`
- `priority`
- `source`
- `channel`
- `campaign`
- `owner_user_public_id`
- `unassigned`
- `active`
- `page`
- `page_size`

O endpoint antigo `GET /leads` continua existindo para compatibilidade.

`LeadRead` agora inclui `created_at` e `updated_at`.

### Banco

Nenhuma migration nova.

### Validação

```powershell
cd C:\Nexyra_CRM
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check app tests alembic

cd C:\Nexyra_CRMrontend
npm run build
```
