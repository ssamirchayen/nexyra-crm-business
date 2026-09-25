# Sprint 3 / Etapa 5 — Recuperação de acesso

## Entregas

- Solicitação pública de recuperação sem enumeração de contas.
- Token criptograficamente aleatório; somente SHA-256 é persistido.
- Expiração configurável e uso único.
- Nova solicitação revoga links anteriores depois do cooldown.
- Redefinição forte de senha e revogação de todas as sessões.
- Auditoria por workspace para solicitação e conclusão.
- Entrega `console` para desenvolvimento local.
- Entrega SMTP opcional usando biblioteca padrão do Python.
- Fluxos frontend `/forgot-password` e `/reset-password`.

## Ambiente local

Com `AUTH_PASSWORD_RESET_DELIVERY=console`, o backend imprime o link no terminal.
Nunca use `console` em produção.

## Produção

Configure `AUTH_PASSWORD_RESET_DELIVERY=smtp` e as variáveis `AUTH_SMTP_*`.
A API pública nunca retorna o token de recuperação.
