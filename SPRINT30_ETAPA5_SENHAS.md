# Sprint 30 — Etapa 5: redefinição administrativa de senha

Pré-requisito: Etapa 4 instalada. Este patch também inclui o Dockerfile com a correção EXE002 para builds feitos no Windows.
Extraia os arquivos na raiz do Nexyra CRM Business, substituindo os correspondentes.
Não há migração nova nem alteração de .env ou banco por script de instalação.

## Como usar

1. Entre como administrador e abra Equipe > membro.
2. Em Redefinir senha, clique em Redefinir senha do membro.
3. Informe SUA senha atual de administrador e confirme a geração.
4. Guarde a senha temporária exibida e entregue-a ao titular por um canal seguro.
5. O titular entra com a senha temporária e deve definir uma nova senha antes de usar o CRM.

Nenhum e-mail ou mensagem é enviado automaticamente. A senha gerada aparece somente na resposta da operação e no painel enquanto ele estiver aberto; não existe consulta posterior da senha. Se fechar o painel antes de guardá-la ou perder a resposta da geração, execute uma nova redefinição, que invalida a senha temporária anterior.

## Regras

- Somente administradores têm members.reset_password.
- A operação exige confirmação da senha atual do administrador e aplica a política de bloqueio por tentativas incorretas do login (configuração padrão: 5 tentativas / 15 minutos).
- Para alterar a própria senha, use Segurança.
- Contas/vínculos inativos não podem receber redefinição por esta operação; reative o acesso primeiro.
- Contas com vínculos a outras empresas, inclusive inativos, são bloqueadas para impedir que um administrador altere uma senha usada em outras empresas.
- Membros ativos ainda sem senha podem receber a primeira senha temporária por este fluxo.
- Todas as sessões anteriores do titular são revogadas, sem o limite de 20 da listagem pessoal. Tokens pendentes de recuperação também são revogados.
- O bloqueio dos tokens é aplicado nas próximas requisições; requisições já em andamento não são canceladas.
- A senha é armazenada apenas como hash. A resposta de geração usa Cache-Control: no-store; a auditoria registra user.password_reset_by_admin sem senha ou token.
- Redefinição, revogações e auditoria são confirmadas na mesma transação. A verificação da senha no login usa bloqueio de credencial para coordenar logins e redefinições.

## Instalação e validação no Windows

Salve o ZIP em Downloads, abra o Docker Desktop e execute no PowerShell:

```powershell
cd "C:\PROJETOS NEXYRA + ATLAS\Nexyra_CRM_Business (multiusuarios)"
Expand-Archive -LiteralPath "$HOME\Downloads\Nexyra_Business_Sprint30_Etapa5_Senhas_PATCH.zip" -DestinationPath . -Force

docker compose -f docker-compose.tests.yml build tests
if ($LASTEXITCODE -ne 0) { throw "Falha no build dos testes." }
docker compose -f docker-compose.tests.yml run --rm tests
if ($LASTEXITCODE -ne 0) { throw "Falha no pytest." }
docker compose -f docker-compose.tests.yml run --rm tests ruff check app tests tools alembic
if ($LASTEXITCODE -ne 0) { throw "Falha no Ruff." }
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\business.ps1 start
```

Abra http://localhost:8080 e pressione Ctrl+F5.
O serviço tests usa SQLite temporário, isolado do PostgreSQL em uso. O comando start também reconstrói o frontend.

## Conferência funcional

Use um membro de teste ativo, vinculado apenas à empresa atual. Abra uma sessão dele em janela anônima; pelo administrador, redefina a senha. Na janela do membro, a próxima requisição deve exigir novo login. Entre com a senha temporária e conclua a troca obrigatória. Confira o evento na Auditoria.

O build do frontend e os testes locais não substituem esta conferência no Windows. Docker Desktop, PostgreSQL, concorrência real e interação visual no navegador não foram executados no ambiente de desenvolvimento.
