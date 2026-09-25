@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\business_backup.ps1" -Action backup
if errorlevel 1 (
  echo Falha no backup. Confira a mensagem acima.
  pause
  exit /b 1
)
pause
