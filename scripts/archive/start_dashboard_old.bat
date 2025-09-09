@echo off
ECHO Lanzando Servicios del Dashboard (Backend y Frontend)...
ECHO.
ECHO Este script DEBE ejecutarse desde la raiz del repositorio (donde reside).
ECHO Asume que 'pip install' y 'npm install' ya se han completado.
ECHO.

REM Guarda el directorio actual (que debe ser la raiz del repositorio)
SET "REPO_ROOT=%CD%"

ECHO [1/2] Lanzando Backend (Gateway) en una nueva ventana...
REM Usamos START con "cmd /K" para lanzar un nuevo proceso en consola y mantener esa ventana abierta.
START "AI Gateway Backend" cmd /K (
    ECHO Estableciendo entorno de Backend...
    cd gateway
    call .venv\Scripts\activate.bat
    
    ECHO Estableciendo PYTHONPATH a la raiz del repositorio: %REPO_ROOT%
    set "PYTHONPATH=%REPO_ROOT%"
    
    ECHO Lanzando Uvicorn (gateway/app/main.py)...
    uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
)

ECHO.
ECHO Esperando 5 segundos a que el backend inicialice...
timeout /t 5 > nul

ECHO.
ECHO [2/2] Lanzando Frontend (WebApp) en una nueva ventana...
START "AGP WebApp Frontend" cmd /K (
    ECHO Estableciendo entorno de Frontend...
    cd webapp
    ECHO Lanzando Vite (npm run dev)...
    npm run dev
)

ECHO.
ECHO Listo. Ambos servicios se estan ejecutando en ventanas de terminal separadas.