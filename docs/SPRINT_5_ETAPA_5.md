# Nexyra CRM — Sprint 5 / Etapa 5

## Triagem e operações em lote

Esta etapa adiciona seleção múltipla de leads e um fluxo seguro de prévia antes de alterações em massa.

### Entregas

- seleção individual de leads na tabela;
- seleção de todos os leads visíveis na página;
- seleção acumulada entre páginas, limitada a 100 leads por operação;
- barra de ações para limpar seleção ou abrir a triagem;
- alteração em lote de status;
- alteração em lote de prioridade;
- atribuição ou remoção de responsável quando o usuário possui `leads.assign`;
- ativação e desativação em lote;
- validação do status contra o pipeline do workspace;
- validação de responsável ativo no workspace;
- simulação (`dry_run`) sem persistência;
- prévia por lead mostrando quais campos realmente mudarão;
- execução atômica após a prévia;
- auditoria individual `lead.batch_updated` para cada lead alterado;
- nenhuma operação de mensageria nesta etapa.

## API

```text
POST /api/v1/workspaces/{workspace_public_id}/leads/batch
```

Exemplo de simulação:

```json
{
  "lead_public_ids": ["LEAD-...", "LEAD-..."],
  "status": "contatado",
  "priority": "alta",
  "owner_mode": "keep",
  "owner_user_public_id": null,
  "active": null,
  "dry_run": true
}
```

Para aplicar, envie o mesmo payload com `dry_run=false`.

## Banco de dados

Esta etapa **não cria migration nova**. O banco continua no head `0018_create_communication_consents`.

## Validação realizada

- `python -m compileall -q app tests` passou;
- 21 testes de triagem/distribuição/SLA/consentimento passaram;
- 39 testes de regressão envolvendo triagem, cadências, inbox, WhatsApp, leads, pipeline e auditoria passaram;
- TypeScript passou com `tsc -b`;
- o `vite build` completo não foi executado neste Linux porque o `node_modules` disponível foi preparado no Windows e não contém `@rollup/rollup-linux-x64-gnu`.

No Windows, valide com:

```powershell
.\.venv\Scripts\python.exe -m ruff check app tests alembic tools
.\.venv\Scripts\python.exe -m pytest -q
cd frontend
npm run build
```
