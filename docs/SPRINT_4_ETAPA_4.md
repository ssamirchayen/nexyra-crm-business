# Sprint 4 / Etapa 4 — Meta / Instagram Lead Ads

## Objetivo

Adicionar o primeiro conector nativo de mídia social ao Nexyra CRM, preservando isolamento por workspace, segurança de credenciais, deduplicação e auditoria.

## Arquitetura

O callback Meta é global no servidor (`/api/v1/meta/webhook`) porque uma aplicação Meta recebe eventos das páginas assinadas no mesmo endpoint. O evento é roteado internamente pela combinação `provider=meta` + `page_id`.

### Segredos

O `Page Access Token` não é salvo em `provider_config`. Ele é criptografado e armazenado em `integration_secrets`. A chave de criptografia vem de `INTEGRATION_SECRET_MASTER_KEY` e não deve ser versionada.

`META_APP_SECRET` e `META_WEBHOOK_VERIFY_TOKEN` também ficam apenas em configuração de servidor.

### Segurança do webhook

- challenge de verificação compara o Verify Token em tempo constante;
- cada POST valida `X-Hub-Signature-256` sobre os bytes originais do corpo;
- o POST público passa pelo rate limit de intake externo em produção;
- eventos que não são `object=page` ou `field=leadgen` são ignorados;
- `page_id` não cadastrado é ignorado;
- Form ID fora da allowlist da fonte é ignorado;
- nenhum access token aparece em URL, auditoria ou resposta da API.

### Normalização de lead

Campos reconhecidos automaticamente:

- `full_name` ou `first_name` + `last_name` → `name`;
- `email` → `email`;
- `phone_number` / `phone` → `phone`;
- campo definido em `interest_field` → `interest`;
- `campaign_name` retornado pela Graph API → `campaign`;
- `message` → `message`;
- `leadgen_id` → `external_id=meta:<id>`.

A deduplicação reaproveita o `LeadService.intake` oficial do CRM.

## Endpoints autenticados

```text
GET    /api/v1/workspaces/{workspace}/integrations/{integration}/meta
PUT    /api/v1/workspaces/{workspace}/integrations/{integration}/meta
DELETE /api/v1/workspaces/{workspace}/integrations/{integration}/meta
POST   /api/v1/workspaces/{workspace}/integrations/{integration}/meta/test
POST   /api/v1/workspaces/{workspace}/integrations/{integration}/meta/subscribe
```

## Endpoints públicos Meta

```text
GET  /api/v1/meta/webhook
POST /api/v1/meta/webhook
```

O POST público não usa sessão do CRM. Sua autenticação é a assinatura HMAC da Meta.
