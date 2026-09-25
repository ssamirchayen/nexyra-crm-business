# Sprint 3 / Etapa 1 — Authentication Foundation

A Etapa 1 cria a infraestrutura de credenciais e sessões do Nexyra CRM.

## Decisões de segurança

1. A senha nunca é armazenada em texto puro.
2. O hash usa PBKDF2-HMAC-SHA256 com salt aleatório por senha.
3. O token entregue ao cliente é opaco e nunca é salvo em texto puro.
4. O banco armazena apenas SHA-256 do token de sessão.
5. Logout e alteração de senha revogam sessões persistidas.
6. O contexto autenticado deriva workspaces e permissões dos memberships ativos.
7. Usuários sem workspace ativo não recebem nova sessão.

## Novas tabelas

- `user_credentials`
- `auth_sessions`

## Compatibilidade

Usuários antigos continuam válidos, mas precisam ter uma senha configurada antes de usar `/auth/login`.
