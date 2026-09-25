# Nexyra CRM — Sprint 4 / Etapa 7

## Caixa de entrada operacional (base omnichannel)

Esta etapa fecha a Sprint 4 transformando a integração de WhatsApp em uma área real de atendimento dentro do CRM.

### O que entrou

- nova página **Caixa de entrada** no menu principal;
- agrupamento das mensagens do WhatsApp em conversas por número e integração;
- vínculo visual com Lead, status, prioridade e responsável;
- histórico cronológico de mensagens recebidas e enviadas;
- status de mensagens enviadas (`sent`, `delivered`, `read`, `failed` e coexistência);
- contador de não lidas por usuário/membership;
- marcação de conversa como lida sem migration nova, usando metadados das mensagens;
- busca por Lead, telefone, integração ou conteúdo recente;
- filtro **Somente não lidas**;
- resposta de texto usando o fluxo seguro **prévia → confirmação → envio** da Etapa 5;
- envio de templates aprovados dentro da conversa usando a Etapa 6;
- arquitetura da API nomeada como `inbox`, pronta para receber outros canais futuramente;
- nenhuma migration nova; o head permanece `0014_create_whatsapp_messages`.

### Endpoints

```text
GET  /api/v1/workspaces/{workspace}/inbox/conversations
GET  /api/v1/workspaces/{workspace}/inbox/conversations/whatsapp/{integration}/{phone}
POST /api/v1/workspaces/{workspace}/inbox/conversations/whatsapp/{integration}/{phone}/read
```

### Segurança

O envio de texto e templates continua reutilizando os tokens de confirmação temporários implementados nas etapas anteriores. A Inbox não cria uma rota paralela de envio e não contorna as validações da integração WhatsApp.

A leitura é controlada por membership usando `inbox_read_by_membership_ids` dentro do `metadata_json` da mensagem recebida. Isso evita uma migration nesta fase e preserva leitura independente entre usuários do workspace.

### Encerramento da Sprint 4

Com esta etapa, a Sprint 4 passa a cobrir o ciclo completo:

```text
Fontes de integração
→ entrada externa
→ Meta Lead Ads
→ WhatsApp Cloud API
→ coexistência com WhatsApp Business App
→ templates aprovados
→ caixa de entrada operacional
```

A próxima sprint recomendada é a **Sprint 5 — Automação Comercial e Inteligência Operacional**, começando pela distribuição inteligente de Leads.
