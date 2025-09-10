@echo off
cls

ECHO ================================================================================
ECHO                    DETENIENDO SISTEMA AI GAMEDEV PIPELINE
ECHO ================================================================================
ECHO.

ECHO [1/5] Deteniendo WebApp Frontend...
taskkill /FI "WindowTitle eq AGP WebApp*" /T /F >nul 2>&1
taskkill /FI "WindowTitle eq *npm run dev*" /T /F >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5173') do taskkill /F /PID %%a >nul 2>&1

ECHO [2/5] Deteniendo Gateway Backend...
taskkill /FI "WindowTitle eq AGP Gateway*" /T /F >nul 2>&1
taskkill /FI "WindowTitle eq *uvicorn*" /T /F >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000') do taskkill /F /PID %%a >nul 2>&1

ECHO [3/5] Deteniendo MCP Unity Bridge...
taskkill /FI "WindowTitle eq MCP Unity Bridge*" /T /F >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5000') do taskkill /F /PID %%a >nul 2>&1

ECHO [4/5] Deteniendo MCP Blender Bridge...
taskkill /FI "WindowTitle eq MCP Blender Bridge*" /T /F >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :9001') do taskkill /F /PID %%a >nul 2>&1

ECHO [5/5] Limpiando procesos residuales...
REM Buscar procesos Python/Node específicos del proyecto
wmic process where "name='python.exe' and commandline like '%%mcp_unity%%'" delete >nul 2>&1
wmic process where "name='python.exe' and commandline like '%%uvicorn%%'" delete >nul 2>&1
wmic process where "name='node.exe' and commandline like '%%vite%%'" delete >nul 2>&1

ECHO.
ECHO ================================================================================
ECHO                         TODOS LOS SERVICIOS DETENIDOS
ECHO ================================================================================
ECHO.
pause