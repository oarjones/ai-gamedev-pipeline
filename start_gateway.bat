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


ECHO [1/1] Lanzando Gateway Backend...
START "AGP Gateway" cmd /k "cd /d %REPO_ROOT%\gateway && uvicorn app.main:app --host 127.0.0.1 --port 8000"


