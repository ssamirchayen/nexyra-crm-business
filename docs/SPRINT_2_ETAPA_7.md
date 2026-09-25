# Nexyra CRM — Sprint 2 / Etapa 7

## Relatórios e Analytics profissionais

A Etapa 7 transforma a rota `/reports` em uma área gerencial conectada aos dados reais do CRM.

### Backend

Novo endpoint:

`GET /api/v1/workspaces/{workspace_public_id}/reports/analytics`

Filtros:

- `period_days`: 7 a 365 dias
- `source`: origem do lead
- `owner_user_public_id`: responsável comercial

Indicadores:

- leads no período
- oportunidades criadas
- pipeline aberto atual
- receita ganha
- ticket médio
- oportunidades ganhas/perdidas
- conversão
- atividades criadas/concluídas/pendentes/atrasadas
- desempenho por origem
- desempenho por vendedor
- distribuição do pipeline
- motivos de perda
- interesses/produtos/cursos
- série de receita

### Frontend

A página Relatórios possui:

- filtros por período, origem e responsável
- cards gerenciais
- gráfico de receita
- desempenho de canais
- pipeline atual
- ranking da equipe
- interesses com resultado
- motivos de perda
- operação de atividades
- exportação CSV

### Banco

Não há migration nova nesta etapa.
