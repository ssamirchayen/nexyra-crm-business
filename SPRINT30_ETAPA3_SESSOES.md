# Sprint 30 — Etapa 3: administração de sessões

Pré-requisito: Business com o PATCH FINAL da Etapa 2 instalado e funcionando.
Este ZIP é incremental: extraia seu conteúdo na raiz do projeto, substituindo os arquivos correspondentes.
Não contém .env, banco de dados ou credenciais e não exige nova migração.

## O que muda

Em Equipe, abra um membro e localize Sessões ativas. Administradores podem consultar até 100 acessos válidos mais recentes e encerrar uma sessão, com confirmação. São exibidos navegador, última atividade e expiração. Sessão válida não significa usuário online.

A permissão sessions.manage é exclusiva do administrador. A API valida a permissão a cada chamada, impede encerrar a própria sessão atual por essa operação e registra revogações na auditoria (session.revoked_by_admin). O token revogado é recusado na próxima requisição; requisições já em andamento não são canceladas. Os outros acessos permanecem válidos.

Como as sessões são globais por usuário, contas com qualquer vínculo a outra empresa, mesmo inativo, não podem ser administradas por este painel. O próprio usuário continua podendo gerenciar seus acessos em Segurança. Gestores, vendedores e operadores não recebem a nova permissão. Nenhum token ou hash é exposto pela listagem.

## Instalar e validar no PowerShell

Salve o ZIP em Downloads (ajuste o caminho se necessário):

```powershell
cd "C:\PROJETOS NEXYRA + ATLAS\Nexyra_CRM_Business (multiusuarios)"
Expand-Archive -LiteralPath "$HOME\Downloads\Nexyra_Business_Sprint30_Etapa3_Sessoes_PATCH.zip" -DestinationPath . -Force

docker compose -f docker-compose.tests.yml build tests
if ($LASTEXITCODE -ne 0) { throw "Falha ao construir a imagem de testes." }
docker compose -f docker-compose.tests.yml run --rm tests
if ($LASTEXITCODE -ne 0) { throw "O pytest encontrou falhas." }
docker compose -f docker-compose.tests.yml run --rm tests ruff check app tests tools alembic
if ($LASTEXITCODE -ne 0) { throw "O Ruff encontrou problemas." }
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\business.ps1 start
```

Abra http://localhost:8080 e atualize com Ctrl+F5. O comando start também reconstrói o frontend; uma falha de TypeScript ou Vite interrompe o build.
Os testes usam SQLite temporário no serviço isolado tests, sem conexão com o PostgreSQL em uso.

## Conferência funcional

1. Entre como administrador e abra Equipe > membro > Ver sessões.
2. Entre com o membro em uma janela anônima; atualize a lista do administrador.
3. Encerre apenas essa sessão. Na janela do membro, uma nova ação que consulte a API deve solicitar novo login.
4. Confira o evento session.revoked_by_admin na auditoria.
5. Uma conta de gestor não deve exibir o painel administrativo de sessões.

## Validação da entrega

O relatório VALIDACAO_ETAPA3.txt contém o resultado do pytest, Ruff e build do frontend executados no ambiente de desenvolvimento.
Docker Desktop e PostgreSQL não estão disponíveis nesse ambiente; valide a instalação com os comandos acima no Windows.
O Vite pode avisar sobre um bundle maior que 500 kB; é um aviso de tamanho, não uma falha de compilação.
