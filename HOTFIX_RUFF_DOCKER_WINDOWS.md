# Correção EXE002 — Docker no Windows

O log recebido contém 216 ocorrências de EXE002: módulos Python chegaram ao
contêiner com permissão de execução, sem shebang. Esses arquivos são importados
ou executados por Python; não precisam do bit de execução.

Este patch atualiza Dockerfile.business.api. Após COPY, o build remove o bit de
execução dos arquivos .py em app, tests, tools e alembic. Diretórios mantêm suas
permissões e nenhuma regra do Ruff é desativada.

Extraia na raiz do Nexyra CRM Business e reconstrua a imagem de testes:

```powershell
cd "C:\PROJETOS NEXYRA + ATLAS\Nexyra_CRM_Business (multiusuarios)"
Expand-Archive -LiteralPath "$HOME\Downloads\Nexyra_Business_Hotfix_Ruff_Docker_Windows.zip" -DestinationPath . -Force

docker compose -f docker-compose.tests.yml build tests
if ($LASTEXITCODE -ne 0) { throw "Falha no build dos testes." }
docker compose -f docker-compose.tests.yml run --rm tests ruff check app tests tools alembic
if ($LASTEXITCODE -ne 0) { throw "Falha no Ruff." }
docker compose -f docker-compose.tests.yml run --rm tests
if ($LASTEXITCODE -ne 0) { throw "Falha no pytest." }
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\business.ps1 start
```

O build é necessário: executar novamente a imagem antiga mantém as permissões
anteriores. O patch não altera dados, credenciais ou configurações de ambiente.

A validação local reproduz a marcação executável em Linux e aplica exatamente
o comando find/chmod usado no Dockerfile. Docker Desktop não foi executado no
ambiente de desenvolvimento; valide a imagem no Windows com os comandos acima.

Reprodução local: 216 erros EXE002 antes da correção; Ruff sem erros depois.

Pytest após a correção: 257 passed, 1 warning in 74.72s (Python 3.12 / Linux).
O aviso é de depreciação do TestClient/Starlette.
