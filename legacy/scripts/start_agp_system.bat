@echo off
setlocal EnableDelayedExpansion
cls

REM ==============================================================================
REM AI GameDev Pipeline - Sistema Unificado de Lanzamiento
REM ==============================================================================
REM Este script lanza todos los componentes necesarios para el sistema AGP:
REM - MCP Unity Bridge (Python)
REM - MCP Blender Bridge (si está disponible)
REM - Gateway Backend (FastAPI)
REM - WebApp Frontend (Vite)
REM - Agente IA (cuando se seleccione un proyecto)
REM ==============================================================================

ECHO ================================================================================
ECHO                    AI GAMEDEV PIPELINE - SISTEMA INTEGRADO
ECHO ================================================================================
ECHO.

REM Verificar que estamos en la raíz del repositorio
if not exist "gateway" (
    ECHO [ERROR] Este script debe ejecutarse desde la raiz del repositorio
    ECHO         Directorio actual: %CD%
    pause
    exit /b 1
)

REM Guardar el directorio raíz
SET "REPO_ROOT=%CD%"

REM Verificar entornos virtuales
ECHO [INFO] Verificando entornos virtuales...
if not exist "gateway\.venv" (
    ECHO [WARN] No se encontro el entorno virtual de Gateway
    ECHO        Ejecuta: cd gateway ^&^& python -m venv .venv ^&^& pip install -r requirements.txt
    pause
    exit /b 1
)

if not exist "webapp\node_modules" (
    ECHO [WARN] No se encontraron las dependencias de WebApp
    ECHO        Ejecuta: cd webapp ^&^& npm install
    pause
    exit /b 1
)

REM ==============================================================================
REM PASO 1: Lanzar MCP Unity Bridge
REM ==============================================================================
ECHO.
ECHO [1/4] Iniciando MCP Unity Bridge...
START "MCP Unity Bridge" /MIN cmd /K (
    cd /d "%REPO_ROOT%"
    set "PYTHONPATH=%REPO_ROOT%\mcp_unity_bridge\src;%PYTHONPATH%"
    if exist ".venv\Scripts\activate.bat" (
        call ".venv\Scripts\activate.bat"
    ) else if exist "gateway\.venv\Scripts\activate.bat" (
        call "gateway\.venv\Scripts\activate.bat"
    )
    ECHO [MCP Unity] Iniciando servidor en puerto 5000...
    python -m mcp_unity_server.main
)

timeout /t 2 >nul

REM ==============================================================================
REM PASO 2: Lanzar MCP Blender Bridge (opcional)
REM ==============================================================================
ECHO [2/4] Verificando Blender...
where blender >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    ECHO       Blender encontrado, iniciando bridge...
    START "MCP Blender Bridge" /MIN cmd /K (
        cd /d "%REPO_ROOT%"
        ECHO [MCP Blender] Iniciando servidor WebSocket...
        blender --background --python mcp_blender_addon\websocket_server.py
    )
) else (
    ECHO       [INFO] Blender no encontrado en PATH, omitiendo...
)

timeout /t 2 >nul

REM ==============================================================================
REM PASO 3: Lanzar Gateway Backend
REM ==============================================================================
ECHO [3/4] Iniciando Gateway Backend...
START "AGP Gateway" /MIN cmd /K (
    cd /d "%REPO_ROOT%\gateway"
    call .venv\Scripts\activate.bat
    set "PYTHONPATH=%REPO_ROOT%"
    ECHO [Gateway] Configurando variables de entorno...
    
    REM Cargar variables desde .env si existe
    if exist ".env" (
        for /f "tokens=1,2 delims==" %%a in (.env) do (
            set "%%a=%%b"
        )
    )
    
    REM Variables por defecto si no están definidas
    if not defined API_KEY set "API_KEY=dev-local-key"
    if not defined GATEWAY_HOST set "GATEWAY_HOST=127.0.0.1"
    if not defined GATEWAY_PORT set "GATEWAY_PORT=8000"
    
    ECHO [Gateway] Iniciando servidor en http://!GATEWAY_HOST!:!GATEWAY_PORT!
    uvicorn app.main:app --host !GATEWAY_HOST! --port !GATEWAY_PORT! --reload
)

ECHO       Esperando a que el backend inicialice...
timeout /t 5 >nul

REM Verificar que el backend está respondiendo
curl -s http://127.0.0.1:8000/health >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    ECHO       [WARN] El backend no responde en /health
    ECHO              Verifica los logs en la ventana "AGP Gateway"
) else (
    ECHO       [OK] Backend respondiendo correctamente
)

REM ==============================================================================
REM PASO 4: Lanzar WebApp Frontend
REM ==============================================================================
ECHO [4/4] Iniciando WebApp Frontend...
START "AGP WebApp" cmd /K (
    cd /d "%REPO_ROOT%\webapp"
    ECHO [WebApp] Iniciando servidor de desarrollo Vite...
    npm run dev
)

timeout /t 3 >nul

REM ==============================================================================
REM RESUMEN Y ACCESOS
REM ==============================================================================
cls
ECHO ================================================================================
ECHO                         SISTEMA AGP INICIADO EXITOSAMENTE
ECHO ================================================================================
ECHO.
ECHO Servicios en ejecucion:
ECHO.
ECHO   [✓] MCP Unity Bridge    : http://127.0.0.1:5000
ECHO   [✓] Gateway Backend     : http://127.0.0.1:8000
ECHO   [✓] WebApp Dashboard    : http://localhost:5173
ECHO   [?] MCP Blender         : ws://127.0.0.1:9001 (si disponible)
ECHO.
ECHO ================================================================================
ECHO.
ECHO Acciones disponibles:
ECHO.
ECHO   1. Abrir Dashboard en el navegador
ECHO   2. Ver documentacion de API (Swagger)
ECHO   3. Monitorear logs del sistema
ECHO   4. Detener todos los servicios
ECHO   5. Salir (mantener servicios ejecutandose)
ECHO.
ECHO ================================================================================

:MENU
ECHO.
SET /P choice="Selecciona una opcion (1-5): "

if "%choice%"=="1" (
    start http://localhost:5173
    goto MENU
)
if "%choice%"=="2" (
    start http://127.0.0.1:8000/docs
    goto MENU
)
if "%choice%"=="3" (
    ECHO.
    ECHO Abriendo ventanas de logs...
    ECHO Presiona Ctrl+C en cada ventana para cerrarla
    pause
    goto MENU
)
if "%choice%"=="4" (
    ECHO.
    ECHO Deteniendo todos los servicios...
    
    REM Detener por título de ventana
    taskkill /FI "WindowTitle eq MCP Unity Bridge*" /T /F >nul 2>&1
    taskkill /FI "WindowTitle eq MCP Blender Bridge*" /T /F >nul 2>&1
    taskkill /FI "WindowTitle eq AGP Gateway*" /T /F >nul 2>&1
    taskkill /FI "WindowTitle eq AGP WebApp*" /T /F >nul 2>&1
    
    REM Detener procesos por puerto
    for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5000') do taskkill /F /PID %%a >nul 2>&1
    for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000') do taskkill /F /PID %%a >nul 2>&1
    for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5173') do taskkill /F /PID %%a >nul 2>&1
    for /f "tokens=5" %%a in ('netstat -aon ^| findstr :9001') do taskkill /F /PID %%a >nul 2>&1
    
    ECHO [OK] Servicios detenidos
    pause
    exit /b 0
)
if "%choice%"=="5" (
    ECHO.
    ECHO Los servicios continuan ejecutandose en segundo plano.
    ECHO Para detenerlos, ejecuta: stop_agp_system.bat
    timeout /t 2 >nul
    exit /b 0
)

ECHO Opcion no valida
goto MENU

endlocal