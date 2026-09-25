# Nexyra CRM — Sprint 5 / Etapa 6

## Mensagens em lote controladas

Esta etapa adiciona envio supervisionado de templates aprovados do WhatsApp para leads selecionados no CRM.

### Fluxo

1. Selecionar até 25 leads na tela de Leads.
2. Abrir **Mensagem** / **Enviar mensagem**.
3. Escolher uma integração WhatsApp ativa.
4. Escolher um template `APPROVED`.
5. Mapear os parâmetros do template usando texto fixo ou variáveis do lead.
6. Gerar a prévia.
7. Revisar elegíveis e bloqueados.
8. Confirmar o envio.

### Proteções

- somente templates aprovados pela Meta;
- limite de 25 leads por lote;
- consentimento e opt-out avaliados antes da prévia;
- revalidação imediatamente antes de cada envio;
- leads inativos ou sem telefone são bloqueados;
- confirmação HMAC expira em 5 minutos;
- qualquer alteração de seleção, telefone, parâmetros ou elegibilidade invalida a confirmação;
- falhas são isoladas por destinatário;
- auditoria consolidada do lote e auditoria individual das mensagens.

### Variáveis disponíveis

- `{{lead_name}}`
- `{{interest}}`
- `{{phone}}`
- `{{email}}`
- `{{campaign}}`
- `{{source}}`
- `{{channel}}`
- `{{status}}`
- `{{priority}}`

### Banco de dados

Nenhuma migration nova. O head permanece em `0018_create_communication_consents`.

### Validação

```powershell
cd C:\Nexyra_CRM

.\.venv\Scripts\python.exe -m ruff check app tests alembic tools --fix
.\.venv\Scripts\python.exe -m ruff check app tests alembic tools
.\.venv\Scripts\python.exe -m pytest -q

cd frontend
npm run build
```
