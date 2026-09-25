# Sprint 4 / Etapa 5 — Embedded Signup + Coexistência

## Fluxo

```text
Nexyra CRM
   ↓ clique em Conectar WhatsApp Business
Facebook JavaScript SDK
   ↓ Embedded Signup / Coexistência
Meta retorna authorization code + session info
   ↓ HTTPS autenticado do Nexyra
Backend troca code por business token
   ↓
Descobre WABA + Phone Number ID
   ↓
Assina a WABA para webhooks
   ↓
Criptografa token
   ↓
WhatsApp Business App + Cloud API coexistem no mesmo número
```

## Endpoints adicionados

```text
GET  /api/v1/workspaces/{workspace}/integrations/{integration}/whatsapp/embedded-signup/config
POST /api/v1/workspaces/{workspace}/integrations/{integration}/whatsapp/embedded-signup/complete
POST /api/v1/workspaces/{workspace}/integrations/{integration}/whatsapp/embedded-signup/select-phone
POST /api/v1/workspaces/{workspace}/integrations/{integration}/whatsapp/coexistence/sync
```

## Eventos

- `messages`: mensagens de clientes + status;
- `smb_message_echoes`: mensagens enviadas no app WhatsApp Business;
- `history`: reconhecido/auditado, sem importação automática;
- `smb_app_state_sync`: reconhecido/auditado, sem importar agenda automaticamente.

A decisão de não importar agenda/histórico automaticamente evita criar leads em massa ou alterar consentimento sem uma ação explícita do operador.
