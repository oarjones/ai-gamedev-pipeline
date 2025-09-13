@echo off
REM Lanzador en modo DEBUG - Todos los servicios en ventanas visibles
cls

ECHO ================================================================================
ECHO                  AI GAMEDEV PIPELINE - MODO DEBUG
ECHO ================================================================================
ECHO.
ECHO Este script lanza cada servicio en una ventana visible para debugging.
ECHO.
pause

SET "REPO_ROOT=%CD%"

ECHO.
ECHO [1/4] Lanzando MCP Unity Bridge...
START "MCP Unity Bridge" cmd /k "cd /d %REPO_ROOT% && set PYTHONPATH=%REPO_ROOT%\mcp_unity_bridge\src && call gateway\.venv\Scripts\activate.bat && echo [MCP Unity Bridge] && echo Servidor en: http://127.0.0.1:5000 && echo. && python -m mcp_unity_server.main"

timeout /t 3 >nul

ECHO [2/4] Lanzando Gateway Backend...
START "AGP Gateway" cmd /k "cd /d %REPO_ROOT%\gateway && call .venv\Scripts\activate.bat && set PYTHONPATH=%REPO_ROOT% && set PATH=%REPO_ROOT%\node_modules\.bin;%APPDATA%\npm;%PATH% && echo [Gateway Backend] && echo API en: http://127.0.0.1:8000 && echo Docs en: http://127.0.0.1:8000/docs && echo. && uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

timeout /t 5 >nul

ECHO [3/4] Lanzando WebApp Frontend...
START "AGP WebApp" cmd /k "cd /d %REPO_ROOT%\webapp && echo [WebApp Frontend] && echo Dashboard en: http://localhost:5173 && echo. && npm run dev"

timeout /t 3 >nul

ECHO [4/4] Verificando Blender (opcional)...
where blender >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    ECHO       Blender encontrado, puedes lanzarlo manualmente si lo necesitas:
    ECHO       blender --background --python mcp_blender_addon\websocket_server.py
) else (
    ECHO       Blender no encontrado (opcional)
)

ECHO.
ECHO ================================================================================
ECHO                         SERVICIOS LANZADOS EN MODO DEBUG
ECHO ================================================================================
ECHO.
ECHO Tienes 4 ventanas abiertas con los servicios:
ECHO   1. MCP Unity Bridge   - http://127.0.0.1:5000
ECHO   2. Gateway Backend    - http://127.0.0.1:8000
ECHO   3. WebApp Frontend    - http://localhost:5173
ECHO.
ECHO Los logs aparecen en tiempo real en cada ventana.
ECHO Para detener un servicio, cierra su ventana o presiona Ctrl+C.
ECHO.
ECHO ================================================================================
ECHO.

timeout /t 5 >nul

ECHO Abriendo el dashboard en el navegador...
start http://localhost:5173

ECHO.
pause
