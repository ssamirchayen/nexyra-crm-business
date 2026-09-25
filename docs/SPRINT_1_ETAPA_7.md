# Sprint 1 / Etapa 7 — Pipeline e oportunidades

## Objetivo

Transformar leads em oportunidades comerciais acompanháveis dentro do funil.

## Oportunidade

Cada oportunidade possui:

- workspace
- lead
- responsável
- título
- valor potencial
- moeda
- etapa
- status
- previsão de fechamento
- motivo de perda
- timestamps de ganho/perda

## Movimentação

A oportunidade só pode ser movida para etapas pertencentes ao pipeline configurado
para o workspace.

Toda movimentação gera um registro em:

`opportunity_stage_history`

Esse histórico registra:

- etapa anterior
- etapa nova
- usuário responsável pela mudança
- observação
- data/hora

## Estados

- `open`
- `won`
- `lost`

Oportunidades encerradas não podem continuar mudando de etapa.

## Métricas iniciais

O endpoint de conversão retorna:

- total de oportunidades
- abertas
- ganhas
- perdidas
- taxa de conversão
- valor total em pipeline
- valor ganho
- ticket médio ganho

## Atlas

Essa estrutura será especialmente útil quando conectarmos o Atlas.

O Atlas poderá futuramente:

- detectar oportunidades paradas
- sugerir mudança de prioridade
- recomendar próxima etapa
- analisar risco de perda
- prever conversão
- sugerir follow-up
- explicar desempenho comercial

As ações executáveis deverão respeitar as permissões já criadas na Etapa 5.

## Próxima etapa

Sprint 1 / Etapa 8 — Atividades e follow-ups.
