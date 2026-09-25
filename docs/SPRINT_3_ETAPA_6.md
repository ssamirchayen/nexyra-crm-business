# Nexyra CRM — Sprint 3 / Etapa 6

## Segurança avançada + preparação de produção

Esta etapa fecha o hardening da Sprint 3 sem alterar o banco.

### Implementado

- headers de segurança em todas as respostas;
- `X-Request-ID` para rastreabilidade técnica;
- `Cache-Control: no-store` nas rotas `/api/v1/auth/*`;
- CORS restrito a origens configuradas, métodos usados pelo CRM e headers necessários;
- `TrustedHostMiddleware` com hosts configuráveis;
- rate limiting adicional por IP nas rotas sensíveis de autenticação;
- validação fail-fast de configuração insegura em `production`;
- bloqueio do token Atlas de desenvolvimento em produção;
- bloqueio de recuperação de senha via console em produção;
- documentação OpenAPI/Swagger desligada automaticamente em produção por padrão;
- HSTS opcional e somente emitido em HTTPS;
- configuração preparada para desktop/local e servidor empresarial.

### CSRF

O CRM continua autenticando o frontend por `Authorization: Bearer` e não por cookie de sessão enviado automaticamente pelo navegador. Por isso não foi adicionado um token CSRF artificial nesta etapa. Se a autenticação for migrada futuramente para cookies, proteção CSRF passa a ser obrigatória no mesmo movimento.

### Rate limit

O limitador desta edição é em memória e é adequado ao modo local/desktop e a um único processo. Em produção horizontal com múltiplos workers/instâncias, substituir o armazenamento por Redis ou equivalente distribuído.

### Banco

Não há migration nova. O head permanece:

`0009_security_hardening`

### Produção

Antes de definir `ENVIRONMENT=production`, configure no mínimo:

- `CORS_ORIGINS` com os domínios reais;
- `SECURITY_ALLOWED_HOSTS` com os hosts reais da API;
- `ATLAS_INTEGRATION_TOKEN` com segredo aleatório de pelo menos 32 caracteres;
- `AUTH_PASSWORD_RESET_DELIVERY=smtp`;
- `AUTH_SMTP_HOST` e `AUTH_SMTP_FROM`.

Ative HSTS apenas quando o servidor estiver realmente atrás de HTTPS.


## Hotfix de validação

O rate limit fica desativado por padrão em `development` para não compartilhar buckets entre testes locais. Em `production`, `SECURITY_RATE_LIMIT_ENABLED=true` é obrigatório e a aplicação falha na inicialização se estiver desativado.
