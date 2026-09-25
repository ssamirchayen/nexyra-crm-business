# Nexyra CRM Desktop 1.0

Esta camada transforma o Nexyra CRM em um aplicativo próprio para Windows.

## O que muda

- O `NexyraCRM.exe` abre uma janela própria do Nexyra CRM.
- Chrome/Edge não é aberto para o uso normal do sistema.
- A interface React continua sendo reaproveitada dentro do Microsoft Edge WebView2.
- FastAPI e o servidor local do frontend sobem em segundo plano e encerram quando a janela é fechada.
- O executável é gerado sem console (`console=False`).
- Banco, configuração, logs e perfil do WebView ficam em `%LOCALAPPDATA%\Nexyra CRM`.
- Migrations continuam automáticas.
- Primeiro acesso continua gerando `PRIMEIRO_ACESSO.txt`.

## Requisito do Windows

O app usa Microsoft Edge WebView2 Runtime, normalmente já presente no Windows 10/11 e em instalações modernas do Edge.

## Build

Execute:

```powershell
cd C:\Nexyra_CRM
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\tools\build_windows_release.ps1
```

Ou use `BUILD_INSTALLER.bat`.

Saídas esperadas:

- `dist\NexyraCRM.exe`
- `release\NexyraCRM_Setup_1.0.0.exe`

## Observação sobre integrações externas

O CRM abre e funciona dentro da janela própria. Alguns provedores externos de autenticação/OAuth podem, por política do próprio provedor, exigir uma janela externa do navegador durante a vinculação de contas. Isso não muda o funcionamento normal do Nexyra como app desktop.
