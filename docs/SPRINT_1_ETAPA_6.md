# Sprint 1 / Etapa 6 — Leads multiempresa

## Objetivo

Construir o primeiro núcleo comercial real do Nexyra CRM.

## Identidade e deduplicação

A deduplicação ocorre somente dentro de uma empresa.

São consideradas identidades:

1. telefone normalizado
2. e-mail normalizado
3. external_id

O mesmo consumidor pode existir em workspaces diferentes.

## Segmentos

O status precisa pertencer ao pipeline configurado para o workspace.

Os `custom_fields` precisam pertencer aos campos permitidos pelo segmento ou
pela configuração personalizada da empresa.

Exemplos:

### Educação

- curso
- turno
- modalidade
- unidade
- bolsa

### Automóveis

- veiculo
- modelo
- ano
- financiamento

### Varejo

- produto
- categoria
- quantidade

## Responsável

Um lead pode ser atribuído a um usuário, mas esse usuário precisa possuir um
membership ativo no mesmo workspace.

## Lead Hub / Atlas

O endpoint:

`POST /api/v1/workspaces/{workspace_id}/leads/intake`

é o primeiro contrato preparado diretamente para a futura integração com o
Nexyra Lead Hub e o Atlas.

O Atlas continuará fora do CRM. A integração ocorrerá via API.

## Próxima etapa

Sprint 1 / Etapa 7 — Pipeline e oportunidades:

- oportunidades
- valor potencial
- etapas
- movimentação no funil
- histórico de mudanças
- ganho/perda
- motivo de perda
- vendedor responsável
- métricas iniciais de conversão
