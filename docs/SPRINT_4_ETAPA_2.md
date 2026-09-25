# Sprint 4 / Etapa 2 — Webhooks + Formulários + API Externa

## Objetivo

Permitir que sistemas externos enviem leads diretamente para uma fonte específica do Nexyra CRM sem usar a sessão de um usuário do CRM e sem acoplar a entrada a um provedor específico.

## Contrato externo

Endpoint:

`POST /api/v1/external/integrations/{integration_public_id}/intake`

Headers:

- `X-Nexyra-Intake-Key` — obrigatório;
- `X-Idempotency-Key` — opcional, até 160 caracteres;
- `X-Request-ID` — opcional; o middleware cria um caso não seja enviado.

A resposta contém somente o necessário para o emissor confirmar o processamento: ação (`created` ou `duplicate_updated`), ID público do lead, source, channel, campanha e contador da fonte.

## Credenciais

Administradores usam:

- `POST /api/v1/workspaces/{workspace}/integrations/{integration}/external-key/rotate`
- `DELETE /api/v1/workspaces/{workspace}/integrations/{integration}/external-key`

A chave tem prefixo `nxy_int_`, é gerada com CSPRNG e é retornada somente na criação/rotação. A aplicação persiste apenas SHA-256 e um pequeno prefixo visual. A comparação usa `hmac.compare_digest`.

Rotacionar a chave invalida a anterior imediatamente. Revogar remove o hash e bloqueia a entrada externa.

## Provedores habilitados nesta etapa

- API / Lead Intake;
- Site e formulários;
- Webhook;
- API personalizada.

CSV não possui intake HTTP. Meta e WhatsApp continuam aguardando os conectores oficiais das etapas específicas.

## Normalização

O intake reconhece aliases comuns, incluindo:

- `name`, `nome`, `full_name`;
- `phone`, `telefone`, `celular`, `whatsapp`;
- `email`;
- `interest`, `interesse`, `curso`, `produto`, `servico`;
- `campaign`, `campanha`, `utm_campaign`;
- `message`, `mensagem`, `observacao`.

Mapeamentos específicos podem ser salvos como metadados não secretos em:

```json
{
  "field_mapping": {
    "name": "contact.fullName",
    "email": "contact.emailAddress",
    "interest": "form.product"
  },
  "custom_field_mapping": {
    "cidade": "contact.city"
  }
}
```

Os caminhos aceitam objetos aninhados usando notação por ponto.

## Regras de segurança

- o remetente externo não pode substituir `source` e `channel`;
- credenciais não entram em `provider_config`;
- a chave bruta nunca é gravada no banco;
- fonte desativada retorna conflito e deixa de receber;
- chave revogada ou incorreta retorna `401` genérico;
- em produção, o rate limiter da Sprint 3 também cobre o intake externo;
- owner/status/priority externos não são aceitos diretamente; defaults de roteamento só podem vir de `routing_config` administrado pelo CRM;
- formulários públicos devem manter a chave no servidor/automação, não no JavaScript exposto ao usuário.

## Idempotência e deduplicação

Quando `X-Idempotency-Key` é enviado e o payload não informa `external_id`, o valor é usado como `external_id`. Assim, reenvios do mesmo webhook entram no mecanismo de deduplicação já existente do Lead Intake e retornam `duplicate_updated` em vez de criar outro lead.

## Observabilidade

Cada intake externo:

- incrementa `intake_count` da fonte;
- atualiza `last_intake_at`;
- registra `integration_source.external_intake_received` na auditoria;
- usa `actor_type=integration`;
- associa request ID, idempotency key e IP remoto aos metadados de auditoria.

## Banco

Migration:

`0011_external_intake_credentials`

Novos campos em `integration_sources`:

- `intake_key_hash`;
- `intake_key_prefix`;
- `intake_count`;
- `last_intake_at`.
