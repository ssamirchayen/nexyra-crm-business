# Nexyra CRM 1.0.0 — Windows Packaging

Arquivos adicionados nesta etapa:

- `desktop_launcher.py` — inicializador do produto empacotado.
- `packaging/nexyra_crm.spec` — configuração do PyInstaller.
- `packaging/NexyraCRM.iss` — projeto do instalador Inno Setup.
- `tools/build_windows_release.ps1` — build automatizado no Windows.
- `docs/WINDOWS_INSTALLER.md` — instruções de empacotamento/instalação.

Para gerar tudo:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\tools\build_windows_release.ps1
```
