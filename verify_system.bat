@echo off
setlocal EnableDelayedExpansion
cls

ECHO ================================================================================
ECHO                  INICIANDO AI GAMEDEV PIPELINE SYSTEM
ECHO ================================================================================
ECHO.

SET REPO_ROOT=%~dp0
pushd "%REPO_ROOT%"

REM Colores para mejor visualización
SET RED=[91m
SET GREEN=[92m
SET YELLOW=[93m
SET BLUE=[94m
SET RESET=[0m

REM ECHO %BLUE%[PASO 1/5]%RESET% Verificando requisitos del sistema...
REM call verify_system.bat >nul 2>&1
REM if %ERRORLEVEL% NEQ 0 (
    REM ECHO %RED%[ERROR]%RESET% El sistema no paso la verificacion. Ejecuta verify_system.bat para detalles.
    REM pause
    REM exit /b 1
REM )
REM ECHO %GREEN%[OK]%RESET% Sistema verificado

ECHO.
ECHO %BLUE%[PASO 2/5]%RESET% Iniciando Gateway Backend...
if not exist "gateway\.venv\Scripts\python.exe" (
    ECHO %YELLOW%[WARN]%RESET% Creando entorno virtual para Gateway...
    pushd gateway
    python -m venv .venv
    call .venv\Scripts\activate.bat
    pip install -r requirements.txt >nul 2>&1
    popd
)

REM Verificar si el puerto 8000 está libre
netstat -an | findstr :8000 | findstr LISTENING >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    ECHO %YELLOW%[WARN]%RESET% Puerto 8000 ya en uso. Intentando liberar...
    for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
        taskkill /PID %%a /F >nul 2>&1
    )
    timeout /t 2 /nobreak >nul
)

SET GATEWAY_TITLE=AGP Gateway [8000]
start "%GATEWAY_TITLE%" /MIN cmd /k "cd /d gateway && call .venv\Scripts\activate.bat && echo %GREEN%Gateway iniciado en http://localhost:8000%RESET% && uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --log-level info"

ECHO %GREEN%[OK]%RESET% Gateway iniciado en puerto 8000
timeout /t 3 /nobreak >nul

ECHO.
ECHO %BLUE%[PASO 3/5]%RESET% Iniciando WebApp Frontend...

REM Instalar dependencias si es necesario
if not exist "webapp\node_modules" (
    ECHO %YELLOW%[WARN]%RESET% Instalando dependencias de WebApp...
    pushd webapp
    npm install >nul 2>&1
    popd
)

REM Verificar si el puerto 5173 está libre
netstat -an | findstr :5173 | findstr LISTENING >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    ECHO %YELLOW%[WARN]%RESET% Puerto 5173 ya en uso. Intentando liberar...
    for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5173 ^| findstr LISTENING') do (
        taskkill /PID %%a /F >nul 2>&1
    )
    timeout /t 2 /nobreak >nul
)

SET WEBAPP_TITLE=AGP WebApp [5173]
start "%WEBAPP_TITLE%" /MIN cmd /k "cd /d webapp && echo %GREEN%WebApp iniciada en http://localhost:5173%RESET% && npm run dev"

ECHO %GREEN%[OK]%RESET% WebApp iniciada en puerto 5173
timeout /t 3 /nobreak >nul

ECHO.
ECHO %BLUE%[PASO 4/5]%RESET% Verificando servicios opcionales...

REM Verificar Unity Bridge (opcional)
ECHO    Verificando Unity Bridge...
curl -s http://localhost:8001/health >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    ECHO    %GREEN%[OK]%RESET% Unity Bridge detectado
) else (
    ECHO    %YELLOW%[INFO]%RESET% Unity Bridge no disponible (opcional)
)

REM Verificar Blender Bridge (opcional)
ECHO    Verificando Blender Bridge...
curl -s http://localhost:8002/health >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    ECHO    %GREEN%[OK]%RESET% Blender Bridge detectado
) else (
    ECHO    %YELLOW%[INFO]%RESET% Blender Bridge no disponible (opcional)
)

ECHO.
ECHO %BLUE%[PASO 5/5]%RESET% Ejecutando health check...
timeout /t 2 /nobreak >nul

curl -s http://localhost:8000/health >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    ECHO %GREEN%[OK]%RESET% Gateway respondiendo correctamente
) else (
    ECHO %RED%[ERROR]%RESET% Gateway no responde. Revisa los logs.
)

ECHO.
ECHO ================================================================================
ECHO                      SISTEMA INICIADO EXITOSAMENTE
ECHO ================================================================================
ECHO.
ECHO %GREEN%Dashboard Web:%RESET%     http://localhost:5173
ECHO %GREEN%API Gateway:%RESET%       http://localhost:8000
ECHO %GREEN%API Docs:%RESET%          http://localhost:8000/docs
ECHO %GREEN%Health Check:%RESET%      http://localhost:8000/health
ECHO.
ECHO %YELLOW%Comandos utiles:%RESET%
ECHO   - Detener todo:    Ctrl+C en cada ventana o ejecuta dev_down.bat
ECHO   - Ver logs:        Las ventanas minimizadas muestran logs en tiempo real
ECHO   - Reiniciar:       Ejecuta dev_down.bat y luego este script nuevamente
ECHO.
ECHO ================================================================================
ECHO.

REM Abrir el navegador automáticamente
SET /P open_browser="Deseas abrir el Dashboard en el navegador? (S/N): "
if /I "!open_browser!"=="S" (
    timeout /t 2 /nobreak >nul
    start http://localhost:5173
)

ECHO.
ECHO Presiona cualquier tecla para mantener esta ventana abierta (logs principales)...
pause >nul

popd
endlocal