# Sprint 1 / Etapa 8 — Atividades e Follow-ups

## Objetivo

Criar a camada operacional de acompanhamento comercial.

## Atividades

O CRM agora registra ligações, mensagens, e-mails, reuniões, tarefas,
follow-ups e observações.

Cada atividade pode possuir:

- workspace
- lead
- oportunidade
- responsável
- tipo
- título
- descrição
- prazo
- status
- data de conclusão
- data de cancelamento

## Estados

- `pending`
- `completed`
- `cancelled`

Somente atividades pendentes podem ser editadas, concluídas ou canceladas.

## Histórico comercial

É possível consultar todas as atividades relacionadas a um lead ou a uma
oportunidade, formando uma linha do tempo operacional básica.

## Fila de pendências

O endpoint:

`GET /api/v1/workspaces/{workspace_id}/follow-ups/pending`

retorna atividades pendentes e informa se cada uma está atrasada.

Essa fila será importante para a inteligência comercial do Atlas.

## Multiempresa

Leads, oportunidades, responsáveis e atividades continuam isolados pelo
workspace. Um usuário de outra empresa não pode ser usado como responsável.

## Próxima etapa

Sprint 1 / Etapa 9 — Auditoria:

- eventos de criação/alteração
- ator responsável
- entidade afetada
- ação
- antes/depois quando aplicável
- timestamp
- base para conformidade e rastreabilidade
