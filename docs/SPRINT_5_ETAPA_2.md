# Nexyra CRM — Sprint 5 / Etapa 2

## SLA + Fila Inteligente de Atendimento

Esta etapa transforma os Leads distribuídos na Etapa 1 em uma fila operacional diária.

### Entregas

- política de SLA por empresa;
- SLA configurável de primeiro contato;
- alerta antecipado antes do estouro;
- identificação de retorno vencido;
- antecipação de follow-ups próximos;
- detecção de Lead sem contato recente;
- fila priorizada por score;
- peso extra para prioridades `alta` e `urgente`;
- filtros por consultor e Leads sem responsável;
- métricas operacionais da fila;
- tela **Fila inteligente** no frontend;
- auditoria de mudanças da política de SLA.

### Como o primeiro contato é identificado

O CRM considera como contato efetivo:

- atividade concluída do tipo ligação, WhatsApp, e-mail, reunião ou follow-up;
- mensagem de WhatsApp enviada e não marcada como falha.

### Migration

A etapa adiciona:

`0016_create_lead_sla_configs`

Execute:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

### Validação

```powershell
.\.venv\Scripts\python.exe -m ruff check app tests alembic tools
.\.venv\Scripts\python.exe -m pytest -q
cd frontend
npm run build
```
