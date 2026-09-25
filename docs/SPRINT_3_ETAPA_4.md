# Nexyra CRM — Sprint 3 / Etapa 4

## Endurecimento de Segurança

Esta etapa fortalece a autenticação introduzida nas Etapas 1–3 e adiciona controles de conta e sessão adequados ao produto comercial.

### Implementado

- bloqueio temporário após tentativas consecutivas de login inválidas;
- limite padrão: 5 falhas e bloqueio de 15 minutos;
- resposta HTTP `429` com `Retry-After` durante o bloqueio;
- limpeza automática do contador após login válido ou redefinição de senha;
- política de novas senhas reforçada:
  - mínimo de 12 caracteres;
  - letra maiúscula;
  - letra minúscula;
  - número;
  - caractere especial;
- senhas iniciais de novos membros passam a ser temporárias e exigem troca no primeiro acesso;
- enquanto `must_change_password=true`, APIs comerciais ficam bloqueadas;
- tela obrigatória de troca de senha no frontend;
- inventário de sessões do usuário;
- registro de IP e User-Agent por sessão;
- encerramento individual de outra sessão;
- encerramento de todas as outras sessões;
- motivo de revogação armazenado no banco;
- atualização de `last_seen_at` limitada a intervalos para evitar escrita em banco a cada request;
- página **Segurança** no CRM para senha e sessões;
- fundação de recuperação de acesso com `password_reset_requests`;
- tokens de recuperação preparados para futura entrega por e-mail/SMS, com apenas o hash armazenado no banco.

### Nova migration

`0009_security_hardening`

A migration preserva credenciais e sessões já existentes ao adicionar os novos campos.

### Importante para usuários existentes

A senha já configurada continua válida, mesmo que tenha sido criada sob a política anterior. A nova política é aplicada quando uma senha for criada, redefinida ou alterada.

### Aplicação

```powershell
cd C:\Nexyra_CRM
.\.venv\Scripts\python.exe -m alembic upgrade head
```

O Alembic deve mostrar:

```text
0009_security_hardening (head)
```

### Validação

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check app tests alembic tools
```

Frontend:

```powershell
cd C:\Nexyra_CRM\frontend
npm run build
npm run dev
```

Acesse **Segurança** na barra lateral ou no menu do usuário.
