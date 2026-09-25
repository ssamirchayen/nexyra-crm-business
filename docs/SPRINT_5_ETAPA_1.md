# Nexyra CRM — Sprint 5 / Etapa 1

## Distribuição inteligente de Leads

A Sprint 5 começa transformando a entrada de Leads em uma fila comercial operável. Leads sem responsável podem ser distribuídos automaticamente entre membros elegíveis da equipe, sem sobrescrever atribuições manuais.

### O que entrou

- motor de distribuição automática integrado ao `LeadService`;
- estratégia **menor carga**, usando a quantidade atual de Leads ativos por consultor;
- estratégia **round-robin**, alternando os membros elegíveis de forma persistente;
- seleção por perfis (`seller`, `operator`, `manager`, `admin`);
- restrição opcional a usuários específicos;
- regras por origem, canal, curso/interesse, campanha e prioridade;
- possibilidade de trocar a estratégia dentro de uma regra;
- direcionamento preferencial para um subconjunto da equipe por regra;
- atribuição automática para Leads novos vindos de criação manual, intake, CSV, Meta, WhatsApp e integrações que reutilizam `LeadService.intake`;
- preservação total de responsável informado manualmente;
- fila para distribuir Leads antigos ainda sem responsável;
- modo **simulação** antes da execução em lote;
- resumo de carga da equipe e quantidade de Leads não atribuídos;
- auditoria de alteração de configuração, atribuição automática e execução em lote;
- novo painel **Distribuição** dentro da página de Leads.

## Estratégias

### Menor carga

Seleciona o membro elegível com menos Leads ativos atribuídos naquele momento. Em empate, usa uma ordem estável da equipe.

### Round-robin

Mantém o último membership utilizado e seleciona o próximo membro elegível. O cursor fica persistido no banco, portanto reiniciar o CRM não reinicia a sequência.

## Regras

As regras são avaliadas na ordem configurada. A primeira regra compatível é aplicada.

Critérios disponíveis:

```text
origem
canal
curso / interesse
campanha
prioridade
```

O campo de curso/interesse também procura valores em `custom_fields`, permitindo que verticais como Educação usem `curso=Radiologia` mesmo quando a informação estiver fora do campo `interest`.

## Segurança operacional

- responsável manual nunca é substituído;
- somente membros e usuários ativos podem receber Leads;
- IDs de usuários configurados são validados contra o workspace;
- atualização da configuração e execução real usam a permissão `leads.assign`;
- consulta de resumo usa `leads.read`;
- distribuição em lote possui prévia sem mutação (`dry_run=true`).

## Endpoints

```text
GET  /api/v1/workspaces/{workspace}/lead-distribution/config
PUT  /api/v1/workspaces/{workspace}/lead-distribution/config
GET  /api/v1/workspaces/{workspace}/lead-distribution/summary
POST /api/v1/workspaces/{workspace}/lead-distribution/run
```

Exemplo de execução:

```json
{
  "limit": 100,
  "dry_run": true
}
```

## Banco de dados

Nova migration:

```text
0015_create_lead_distribution_configs
```

Ela cria `lead_distribution_configs`, uma configuração por workspace, contendo estratégia, equipe elegível, regras e cursor do round-robin.

## Validação feita no pacote

Backend:

```text
185 testes coletados
185 passaram em execuções segmentadas
```

Frontend:

```text
npx tsc -b
```

A validação TypeScript passou. O `vite build` completo não pode terminar no ambiente Linux usado para montar o pacote porque o `node_modules` disponível foi preparado no Windows e não contém o binário opcional `@rollup/rollup-linux-x64-gnu`. No Windows do projeto, `npm run build` continua sendo a validação final correta.

## Instalação / atualização

Depois de extrair o pacote sobre `C:\Nexyra_CRM`, rode:

```powershell
cd C:\Nexyra_CRM
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m ruff check app tests alembic tools
.\.venv\Scripts\python.exe -m pytest -q

cd frontend
npm run build
```

Depois abra **Leads → Distribuição**.
