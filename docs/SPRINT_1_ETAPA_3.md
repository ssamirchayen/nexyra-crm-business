# Sprint 1 / Etapa 3 — Workspaces multiempresa

Esta etapa transforma `workspaces` em um módulo real de empresas do Nexyra CRM.

Endpoints:

- `POST /api/v1/workspaces`
- `GET /api/v1/workspaces`
- `GET /api/v1/workspaces/{public_id}`
- `PATCH /api/v1/workspaces/{public_id}`
- `POST /api/v1/workspaces/{public_id}/deactivate`

O `public_id` será usado externamente, evitando expor o ID inteiro interno do banco.

Próxima etapa: segmentos configuráveis por workspace.
