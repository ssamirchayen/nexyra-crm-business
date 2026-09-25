# Sprint 4 / Etapa 1 — Central de Integrações + Fontes de Leads

## Objetivo

Criar a fundação persistente da Sprint 4 para que cada workspace do Nexyra CRM possa cadastrar e administrar suas fontes de captação sem acoplar o CRM a um provedor específico.

## Backend

- novo catálogo de provedores: API/Lead Intake, site/formulários, webhook, CSV, API personalizada, Meta e WhatsApp;
- nova entidade `IntegrationSource`, isolada por workspace;
- CRUD base de fonte: listar, criar, atualizar, ativar e desativar;
- `source`, `channel` e campanha padrão por fonte;
- `routing_config` reservado para regras de roteamento das próximas etapas;
- `provider_config` aceita somente metadados não secretos; chaves com token, senha, secret ou API key são rejeitadas;
- auditoria para criação, alteração, ativação e desativação;
- endpoint de intake específico por fonte, que força `source` e `channel` cadastrados e aplica campanha padrão quando o lead recebido não informa campanha;
- fontes desativadas não podem receber leads.

## API

- `GET /api/v1/workspaces/{workspace}/integrations/overview`
- `GET /api/v1/workspaces/{workspace}/integrations/catalog`
- `GET /api/v1/workspaces/{workspace}/integrations`
- `POST /api/v1/workspaces/{workspace}/integrations`
- `PATCH /api/v1/workspaces/{workspace}/integrations/{integration}`
- `POST /api/v1/workspaces/{workspace}/integrations/{integration}/activate`
- `POST /api/v1/workspaces/{workspace}/integrations/{integration}/deactivate`
- `POST /api/v1/workspaces/{workspace}/integrations/{integration}/intake`

A central usa as permissões já consolidadas da Sprint 3: `settings.read`, `settings.update` e `leads.create`.

## Frontend

A seção **Configurações → Integrações** deixa de ser somente um placeholder e passa a consumir a API real:

- catálogo de provedores e estado de disponibilidade;
- endpoint real do Lead Intake;
- cadastro de fontes por workspace;
- origem, canal e campanha padrão;
- quantidade de fontes ativas;
- listagem das fontes configuradas;
- ativação/desativação preservando histórico;
- cópia do endpoint de intake específico de cada fonte.

Meta e WhatsApp aparecem como preparação de fonte, sem fingir conexão OAuth. Os conectores oficiais serão implementados nas etapas específicas da Sprint 4.

## Segurança

Esta etapa não armazena access tokens, senhas, client secrets ou API keys em `integration_sources`. Credenciais reais deverão entrar em mecanismo próprio nas etapas dos conectores.

O intake de fonte continua protegido pela autenticação/permissão do CRM nesta etapa. Webhooks públicos assinados e OAuth pertencem às próximas etapas.

## Banco de dados

Migration obrigatória:

`0010_create_integration_sources`

Executar:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```
