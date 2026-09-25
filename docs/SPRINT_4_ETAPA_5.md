# Sprint 4 / Etapa 5 — WhatsApp Cloud API

## Objetivo

Adicionar ao Nexyra CRM um conector nativo da WhatsApp Cloud API para atendimento comercial, preservando isolamento por workspace, credenciais criptografadas, auditoria, idempotência e confirmação explícita antes de envios.

## Arquitetura

O callback WhatsApp é global no servidor (`/api/v1/whatsapp/webhook`). Eventos são roteados internamente por `metadata.phone_number_id`, que identifica uma única `IntegrationSource` ativa do provedor `whatsapp`.

### Credenciais

O Access Token não é salvo em `provider_config`. Ele é criptografado em `integration_secrets` usando `INTEGRATION_SECRET_MASTER_KEY`.

O servidor mantém separadamente:

- `WHATSAPP_APP_SECRET` — assinatura HMAC do webhook;
- `WHATSAPP_WEBHOOK_VERIFY_TOKEN` — challenge de configuração;
- versão/base URL da Graph API e timeout.

Nenhum desses segredos é devolvido por endpoints de status.

## Persistência de mensagens

A migration `0014_create_whatsapp_messages` cria `whatsapp_messages` com:

- workspace;
- fonte de integração;
- Lead opcional;
- ID da mensagem do provedor;
- direção (`inbound` / `outbound`);
- tipo;
- remetente/destinatário;
- corpo;
- status e erro;
- timestamp do provedor;
- metadados técnicos;
- timestamps locais.

`provider_message_id` é único, oferecendo idempotência para redelivery de webhooks.

## Entrada de mensagens

Tipos tratados nesta etapa:

- texto;
- button;
- interactive (`button_reply` / `list_reply`);
- location;
- mídia com caption;
- outros tipos como marcador `[tipo]`.

Para cada mensagem válida:

1. identifica a fonte pelo `phone_number_id`;
2. normaliza o telefone do remetente;
3. aproveita o nome enviado em `contacts.profile.name` quando disponível;
4. executa `LeadService.intake`;
5. grava `WhatsAppMessage`;
6. grava uma `Activity` concluída do tipo `whatsapp`;
7. atualiza contador/último intake da fonte;
8. audita como ator `integration`.

## Status de entrega

Eventos `statuses` procuram a mensagem por `provider_message_id` e atualizam status, timestamp, código e mensagem de erro quando fornecidos pela Meta.

## Saída com confirmação

Envio de texto é dividido em dois endpoints. A prévia gera um token HMAC de vida curta que vincula:

- Integration Source;
- destinatário normalizado;
- texto exato;
- expiração.

O endpoint de envio valida o token antes de chamar a Graph API. Alterar texto ou destinatário invalida a confirmação.

## Endpoints autenticados

```text
GET    /api/v1/workspaces/{workspace}/integrations/{integration}/whatsapp
PUT    /api/v1/workspaces/{workspace}/integrations/{integration}/whatsapp
DELETE /api/v1/workspaces/{workspace}/integrations/{integration}/whatsapp
POST   /api/v1/workspaces/{workspace}/integrations/{integration}/whatsapp/test
POST   /api/v1/workspaces/{workspace}/integrations/{integration}/whatsapp/subscribe
POST   /api/v1/workspaces/{workspace}/integrations/{integration}/whatsapp/messages/preview
POST   /api/v1/workspaces/{workspace}/integrations/{integration}/whatsapp/messages/send
GET    /api/v1/workspaces/{workspace}/integrations/{integration}/whatsapp/messages
```

Permissões:

- leitura/status/mensagens: `settings.read`;
- configuração/teste/assinatura/desconexão: `settings.update`;
- prévia/envio: `activities.create`.

## Endpoints públicos

```text
GET  /api/v1/whatsapp/webhook
POST /api/v1/whatsapp/webhook
```

O POST público não usa sessão do CRM. Sua autenticidade é validada por `X-Hub-Signature-256` usando o App Secret.

## Segurança

- comparação segura do Verify Token;
- HMAC-SHA256 sobre bytes originais do POST;
- rate limit do webhook em produção;
- Access Token criptografado;
- bloqueio de Phone Number ID duplicado entre fontes ativas;
- confirmação curta e assinada para saída;
- segredos não entram em auditoria;
- isolamento de workspace mantido nos endpoints autenticados.

## Limitação consciente desta etapa

O envio implementado é de texto livre. A WhatsApp Cloud API impõe janela de atendimento e pode exigir templates aprovados fora dela. Templates, mídia de saída e uma caixa de entrada conversacional completa podem ser evoluídos em etapas futuras sem alterar o contrato principal criado aqui.
