@echo off
setlocal
cd /d "%~dp0"
echo.
echo ========================================
echo      NEXYRA CRM - BUILD WINDOWS
echo ========================================
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\tools\build_windows_release.ps1"
echo.
if errorlevel 1 (
  echo Build finalizado com erro.
) else (
  echo Build finalizado com sucesso.
)
echo.
pause
endlocal
