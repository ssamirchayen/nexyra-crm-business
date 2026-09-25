# Sprint 3 / Etapa 3 — Proteção das APIs + RBAC

## Objetivo

Aplicar a autenticação da Sprint 3 às APIs comerciais do Nexyra CRM, isolando empresas e validando permissões por papel.

## Proteções aplicadas

- `401` quando existe autenticação configurada e a chamada não possui sessão Bearer válida.
- `403` quando o usuário autenticado não pertence ao workspace solicitado.
- `403` quando o papel do usuário não possui a permissão necessária.
- listagem de workspaces limitada às empresas ativas do usuário autenticado.
- criação de nova empresa por usuário autenticado cria automaticamente um vínculo `admin` para o criador.
- atribuição de responsável para outro usuário exige `leads.assign`; o usuário pode atribuir a si próprio.
- operações autenticadas passam a registrar o usuário real como ator da auditoria.
- movimentos/ganhos/perdas de oportunidade usam o usuário autenticado como `changed_by`, impedindo personificação pelo payload.

## Permissões utilizadas

- workspace: `workspace.read`, `workspace.update`
- equipe: `members.read`, `members.create`, `members.update`, `members.deactivate`
- leads: `leads.read`, `leads.create`, `leads.update`, `leads.assign`
- pipeline/oportunidades: `pipeline.read`, `pipeline.update`
- atividades: `activities.read`, `activities.create`, `activities.update`
- relatórios: `analytics.read`
- auditoria: `audit.read`
- configurações: `settings.update` para alteração do segmento/pipeline

## Bootstrap controlado

Para não bloquear instalações antigas antes da configuração do primeiro administrador, existe um modo de bootstrap **somente enquanto a tabela de credenciais não possui nenhuma senha configurada**.

Assim que a primeira credencial é criada, as APIs protegidas passam a exigir autenticação automaticamente. Em uma instalação já migrada, como a instalação atual, a proteção entra em vigor imediatamente.

## Atlas

As rotas `/integrations/atlas/*` continuam usando o contrato de integração próprio (`X-Nexyra-Integration-Token` + ator), sem serem substituídas pelo token de sessão do frontend.

## Banco

Nenhuma migration nova nesta etapa. O head continua `0008_create_auth_foundation`.
