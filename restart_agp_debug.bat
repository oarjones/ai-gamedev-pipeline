@echo off
REM Reinicio rápido de servicios lanzados por start_agp_debug.bat
REM - Cierra ventanas "MCP Unity Bridge", "AGP Gateway", "AGP WebApp"
REM - Vuelve a lanzar start_agp_debug.bat

setlocal ENABLEEXTENSIONS
set "REPO_ROOT=%~dp0"
cd /d "%REPO_ROOT%"

echo ================================================================================
echo                AGP - REINICIO DE SERVICIOS (stop + start)
echo ================================================================================

set TIT1=MCP Unity Bridge
set TIT2=AGP Gateway
set TIT3=AGP WebApp

echo [1/3] Cerrando ventanas existentes (si las hay)...

REM Intento 1: taskkill por titulo exacto (mata el arbol con /T)
for %%T in ("%TIT1%" "%TIT2%" "%TIT3%") do (
  taskkill /FI "WINDOWTITLE eq %%~T" /F /T >nul 2>&1
)

REM Intento 2 (fallback): PowerShell por coincidencia parcial en el titulo
for %%T in ("%TIT1%" "%TIT2%" "%TIT3%") do (
  powershell -NoProfile -Command "Get-Process -Name cmd -ErrorAction SilentlyContinue ^| Where-Object { $_.MainWindowTitle -like '*%%~T*' } ^| ForEach-Object { try { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue } catch {} }" >nul 2>&1
)

REM Pausa breve para liberar puertos
timeout /t 2 >nul

echo [2/3] Relanzando servicios en modo DEBUG...
if exist "%REPO_ROOT%start_agp_debug.bat" (
  call "%REPO_ROOT%start_agp_debug.bat"
) else (
  echo ERROR: No se encuentra start_agp_debug.bat en "%REPO_ROOT%".
  echo Aborta.
  exit /b 1
)

echo [3/3] Reinicio solicitado. Revisa las nuevas ventanas y logs.
echo.
endlocal
exit /b 0

