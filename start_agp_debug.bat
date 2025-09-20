@echo off
REM Lanzador en modo DEBUG - Todos los servicios en ventanas visibles
cls

ECHO ================================================================================
ECHO                  AI GAMEDEV PIPELINE - MODO DEBUG
ECHO ================================================================================
ECHO.
ECHO Este script lanza cada servicio en una ventana visible para debugging.
ECHO.

SET "REPO_ROOT=%CD%"

ECHO.
ECHO [1/2] Lanzando MCP Unity Bridge...
START "MCP Unity Bridge" cmd /k "cd /d %REPO_ROOT% && set PYTHONPATH=%REPO_ROOT%\mcp_unity_bridge\src && call gateway\.venv\Scripts\activate.bat && echo [MCP Unity Bridge] && echo Servidor en: http://127.0.0.1:5000 && echo. && python -m mcp_unity_server.main"

timeout /t 3 >nul


ECHO [2/2] Lanzando WebApp Frontend...
START "AGP WebApp" cmd /k "cd /d %REPO_ROOT%\webapp && echo [WebApp Frontend] && echo Dashboard en: http://localhost:5173 && echo. && npm run dev"

timeout /t 3 >nul


@REM ECHO.
@REM ECHO ================================================================================
@REM ECHO                         SERVICIOS LANZADOS EN MODO DEBUG
@REM ECHO ================================================================================
@REM ECHO.
@REM ECHO Tienes 4 ventanas abiertas con los servicios:
@REM ECHO   1. MCP Unity Bridge   - http://127.0.0.1:5000
@REM ECHO   2. Gateway Backend    - http://127.0.0.1:8000
@REM ECHO   3. WebApp Frontend    - http://localhost:5173
@REM ECHO.
@REM ECHO Los logs aparecen en tiempo real en cada ventana.
@REM ECHO Para detener un servicio, cierra su ventana o presiona Ctrl+C.
@REM ECHO.
@REM ECHO ================================================================================
@REM ECHO.


ECHO Abriendo el dashboard en el navegador...
start http://localhost:5173

ECHO.