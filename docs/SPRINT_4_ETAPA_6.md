# Sprint 4 / Etapa 6 — WhatsApp Message Templates

## Objetivo

Adicionar suporte nativo e seguro a templates aprovados da WhatsApp Cloud API sem liberar disparo em massa automático.

## Fluxo

```text
WABA configurada
   ↓
GET /message_templates
   ↓
filtra APPROVED
   ↓
Nexyra identifica corpo + {{variáveis}}
   ↓
operador informa telefone e valores
   ↓
prévia renderizada
   ↓
confirmação HMAC de 5 minutos
   ↓
POST /{phone_number_id}/messages type=template
   ↓
WhatsAppMessage + Activity + Audit
```

## Contrato suportado nesta etapa

O Nexyra suporta templates que:

- estejam com status `APPROVED`;
- usem texto estático ou variáveis sequenciais no corpo (`{{1}}`, `{{2}}`...);
- não exijam cabeçalho dinâmico de imagem, vídeo, documento ou localização;
- não exijam parâmetros dinâmicos fora do corpo.

A limitação é intencional: templates fora desse contrato aparecem como não suportados e não são enviados parcialmente.

## Endpoints

### Listagem

```text
GET /workspaces/{workspace}/integrations/{integration}/whatsapp/templates
```

Retorna nome, idioma, categoria, corpo, quantidade de parâmetros e compatibilidade com o envio controlado.

### Prévia

```text
POST /workspaces/{workspace}/integrations/{integration}/whatsapp/templates/preview
```

Exemplo:

```json
{
  "to": "5592999999999",
  "template_name": "retorno_lead",
  "language_code": "pt_BR",
  "parameters": ["Maria", "Radiologia"]
}
```

O backend consulta novamente o template aprovado, valida os parâmetros, renderiza o corpo e emite um token de confirmação temporário.

### Envio

```text
POST /workspaces/{workspace}/integrations/{integration}/whatsapp/templates/send
```

O token precisa corresponder exatamente ao destinatário e ao conteúdo aprovado na prévia.

## Persistência

Nenhuma tabela nova é necessária. O envio entra em `whatsapp_messages` como:

```text
direction = outbound
message_type = template
status = sent
```

Os detalhes do template ficam em `metadata_json`.

## Próxima evolução natural

Com texto livre, coexistência e templates individuais cobertos, a próxima evolução pode trabalhar a camada operacional: caixa de entrada unificada, filas/SLA, distribuição de atendimento, consentimento/opt-out e automações Atlas, sem acoplar o Core do Atlas diretamente à API da Meta.
