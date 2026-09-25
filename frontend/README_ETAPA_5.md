# Sprint 2 / Etapa 5 — Atividades e Follow-ups

## Entrega

- tela profissional de atividades
- fila priorizada de follow-ups
- busca e filtros
- paginação
- criação e edição
- conclusão e cancelamento
- vínculo com lead e oportunidade
- responsável comercial
- detecção de atraso
- métricas operacionais
- estados de loading, erro e vazio

## Backend

Novo endpoint de apoio ao frontend:

`GET /api/v1/workspaces/{workspace_public_id}/activities/search`

Filtros: `q`, `activity_type`, `status`, `owner_user_public_id`, `unassigned`, `overdue`, `due_from`, `due_to`, `page`, `page_size`.

Não há migration nova.
