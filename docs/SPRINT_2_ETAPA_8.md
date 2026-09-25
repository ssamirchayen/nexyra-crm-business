# Nexyra CRM — Sprint 2 / Etapa 8

## Auditoria profissional no frontend

Esta etapa transforma a trilha de auditoria já existente no backend em uma área operacional e gerencial do CRM.

## Backend

Novo endpoint:

`GET /api/v1/workspaces/{workspace_public_id}/audit/search`

Filtros suportados:

- busca textual (`q`)
- origem do evento (`actor_type`)
- usuário responsável (`actor_user_public_id`)
- tipo de entidade (`entity_type`)
- ID da entidade (`entity_public_id`)
- ação (`action`)
- intervalo de data/hora (`created_from`, `created_to`)
- paginação (`page`, `page_size`)

O endpoint também devolve:

- contagem total
- contagem por origem (`system`, `user`, `atlas`, `integration`)
- ações disponíveis
- entidades disponíveis
- atores disponíveis
- nome e função do usuário responsável quando a auditoria possui vínculo de ator

O endpoint legado `/audit` continua compatível.

## Frontend

A nova tela de Auditoria contém:

- indicadores de volume por origem
- pesquisa
- filtros por período, origem, usuário, entidade e ação
- tabela paginada
- identificação de evento, entidade e responsável
- drawer lateral de detalhes
- comparação antes/depois por campo
- snapshots JSON completos
- metadados técnicos
- identificação visual de eventos de sistema, usuário, Atlas e integrações

## Segurança e rastreabilidade

A auditoria preserva a origem técnica e os snapshots das alterações. Enquanto a autenticação real do CRM ainda não estiver implementada, ações gerais executadas sem sessão autenticada continuam registradas como `system`. Eventos que já possuem identidade explícita mantêm o usuário associado.

## Banco

Não há migration nova nesta etapa.
