# Sprint 30 — Etapa 4: permissões da equipe

Pré-requisito: Etapa 3 instalada e funcionando. Patch incremental para Nexyra CRM Business.
Extraia na raiz do projeto, substituindo os arquivos. Não há nova migração nem alteração de configuração.

## Regras

| Perfil | Gestão da equipe |
| --- | --- |
| Administrador | Cria e edita todos os perfis; desativa e reativa membros; administra sessões conforme a Etapa 3. |
| Gestor | Cria e edita vendedores e operadores. Não gerencia gestores ou administradores e não altera o status dos vínculos. |
| Vendedor e operador | Consultam a equipe; não criam, editam ou desativam membros. |

A API aplica as regras mesmo quando uma requisição é enviada fora da interface.
A troca do próprio perfil pede confirmação e atualiza a sessão da interface após a mudança.
As operações de alteração continuam registradas na auditoria.

A empresa não pode perder seu último administrador ativo. Antes de desativá-lo ou mudar sua função, configure outro administrador ativo com senha. Um vínculo inativo, uma conta globalmente inativa ou um administrador sem senha não serve como substituto de um administrador que já tem credencial.

No PostgreSQL, as alterações de membros obtêm um bloqueio na linha da empresa antes da validação para serializar alterações concorrentes de administradores. O ator é consultado novamente após esse bloqueio.
A preparação local inicial sem credenciais continua disponível. Estas mudanças não alteram os fluxos de provisionamento local existentes.

## Instalação no PowerShell

Salve o ZIP em Downloads, abra o Docker Desktop e execute:

```powershell
cd "C:\PROJETOS NEXYRA + ATLAS\Nexyra_CRM_Business (multiusuarios)"
Expand-Archive -LiteralPath "$HOME\Downloads\Nexyra_Business_Sprint30_Etapa4_Permissoes_PATCH.zip" -DestinationPath . -Force

docker compose -f docker-compose.tests.yml build tests
if ($LASTEXITCODE -ne 0) { throw "Falha no build dos testes." }
docker compose -f docker-compose.tests.yml run --rm tests
if ($LASTEXITCODE -ne 0) { throw "Falha no pytest." }
docker compose -f docker-compose.tests.yml run --rm tests ruff check app tests tools alembic
if ($LASTEXITCODE -ne 0) { throw "Falha no Ruff." }
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\business.ps1 start
```

Atualize http://localhost:8080 com Ctrl+F5.
Os testes são executados no serviço isolado tests, usando SQLite temporário e sem acesso ao banco PostgreSQL em uso.
O comando start reconstrói também o frontend.

## Conferência no Windows

- Administrador: verifique os controles de criação, edição e status. Tentar remover o último administrador deve mostrar uma mensagem explicativa.
- Gestor: abra um vendedor; o formulário deve oferecer apenas Vendedor e Operador e não mostrar alteração de status. Gestores e administradores não devem exibir botões de edição para esse perfil.
- Vendedor/operador: a equipe permanece visível, sem botões de criação ou edição.
- Verifique se a gestão de sessões da Etapa 3 continua disponível para administradores.

## Validação

Consulte VALIDACAO_ETAPA4.txt. Testes automatizados e build executados em Linux/Python 3.12.
Docker Desktop, PostgreSQL e interação visual no navegador devem ser conferidos no ambiente Windows. A concorrência real no PostgreSQL não foi exercitada neste ambiente.
