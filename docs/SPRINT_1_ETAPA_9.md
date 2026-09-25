# Sprint 1 / Etapa 9 — Auditoria

## Objetivo

Criar rastreabilidade das ações relevantes do Nexyra CRM.

## Modelo

Tabela:

`audit_events`

Cada evento contém:

- `public_id`
- `workspace_id`
- `actor_membership_id`
- `actor_type`
- `entity_type`
- `entity_public_id`
- `action`
- `before_data`
- `after_data`
- `metadata_json`
- `created_at`

## Antes e depois

Quando uma entidade é alterada, a auditoria preserva um snapshot anterior e
um snapshot posterior.

Isso permite responder perguntas como:

- qual era o status anterior do lead?
- quem movimentou a oportunidade?
- qual era o papel anterior do vendedor?
- quando uma tarefa foi concluída?
- qual foi a etapa anterior e a nova etapa do funil?

## Isolamento

Toda consulta de auditoria é vinculada ao workspace.

Eventos de uma empresa não são retornados no histórico de outra.

## Atlas

A tabela foi preparada para que eventos futuros possam identificar o tipo de ator.

Exemplos futuros:

- `actor_type=atlas`
- `actor_type=integration`

Isso será importante para distinguir ações humanas, automações e ações
executadas pelo Atlas.

## Observação de segurança

Enquanto a autenticação real não estiver implementada, a auditoria registra
com precisão o que ocorreu no sistema, mas operações sem identidade
autenticada ficam classificadas como `system`.

A prova forte de identidade do usuário depende da futura camada de
autenticação/sessão.

## Próxima etapa

Sprint 1 / Etapa 10 — Atlas Integration Contract + validação final.

Essa etapa fechará a Sprint 1 com:

- contrato de integração Atlas ↔ Nexyra CRM
- endpoints seguros de leitura/contexto
- contrato de ações
- health/capabilities
- preparação do Lead Hub
- versionamento do contrato
- testes de integração
- validação final da Sprint 1
