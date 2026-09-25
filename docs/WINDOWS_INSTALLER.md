# Nexyra CRM — Executável e instalador para Windows

## Objetivo

Esta etapa transforma o Nexyra CRM web local em uma entrega executável para Windows.

O `NexyraCRM.exe`:

1. cria a pasta de dados em `%LOCALAPPDATA%\Nexyra CRM`;
2. gera uma configuração local segura na primeira execução;
3. preserva `.env` e banco entre atualizações;
4. aplica as migrations Alembic automaticamente;
5. inicia a API em `127.0.0.1:8000`;
6. serve o frontend em `127.0.0.1:5173`;
7. abre o navegador no Nexyra CRM.
8. em uma instalação vazia, cria um administrador inicial com senha temporária obrigatoriamente trocada no primeiro login.

Os dados do cliente **não ficam dentro da pasta de instalação**, evitando perda de banco ao atualizar/desinstalar o executável.

## Gerar no Windows

Na raiz do projeto:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\tools\build_windows_release.ps1
```

O script executa Ruff, pytest, build do frontend, PyInstaller e um smoke test do `.exe`.

Saída portátil:

```text
dist\NexyraCRM.exe
```

## Gerar instalador

Instale Inno Setup 6, se ainda não estiver instalado:

```powershell
winget install -e --id JRSoftware.InnoSetup
```

Depois execute novamente:

```powershell
.\tools\build_windows_release.ps1
```

Saída:

```text
release\NexyraCRM_Setup_1.0.0.exe
```

## Dados locais

Persistem em:

```text
%LOCALAPPDATA%\Nexyra CRM
```

Principais arquivos:

```text
.env
nexyra_crm.db
PRIMEIRO_ACESSO.txt   # somente quando um admin inicial é criado
logs\launcher.log
```

Na primeira instalação vazia, o launcher abre `PRIMEIRO_ACESSO.txt` com o e-mail e a senha temporária. Depois de entrar e trocar a senha, apague esse arquivo.

O desinstalador não apaga esses dados automaticamente.

## Meta / WhatsApp

Credenciais Meta, WhatsApp e SMTP continuam configuradas no `.env` local. Não devem ser incorporadas ao executável.

## Observação sobre assinatura digital

O instalador e o executável gerados localmente não terão assinatura Authenticode por padrão. Para distribuição pública, a etapa posterior recomendada é assinar o `.exe` e o instalador com um certificado de code signing.

## Reaproveitar o banco atual

Se quiser levar os dados que já estão em `C:\Nexyra_CRM\nexyra_crm.db` para a instalação empacotada, antes de abrir o executável instalado rode:

```powershell
.\tools\import_current_database.ps1
```

Ou informe outro banco:

```powershell
.\tools\import_current_database.ps1 -Source "C:\caminho\meu_banco.db"
```

O script faz backup do banco de destino quando ele já existe.
