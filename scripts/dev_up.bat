@echo off
setlocal ENABLEDELAYEDEXPANSION
REM AI GameDev Pipeline - Dev Up (Windows)

set REPO_ROOT=%~dp0\..
pushd "%REPO_ROOT%"

REM Backend (gateway)
if not exist "gateway\.venv\Scripts\python.exe" (
  echo [dev_up] Creating Python venv for gateway...
  pushd gateway
  python -m venv .venv
  call .venv\Scripts\activate.bat
  pip install -e .
  popd
)

REM Ensure mcp_unity_bridge is installed in gateway venv (editable)
if exist "mcp_unity_bridge\pyproject.toml" (
  echo [dev_up] Ensuring mcp_unity_bridge is installed in gateway venv...
  pushd gateway
  call .venv\Scripts\activate.bat
  pip install -e ..\mcp_unity_bridge >nul
  popd
)

REM Start Gateway (Uvicorn)
set GATEWAY_TITLE=AGP Gateway
start "!GATEWAY_TITLE!" cmd /k "cd /d gateway && call .venv\Scripts\activate.bat && set PYTHONPATH=%REPO_ROOT%;%REPO_ROOT%\mcp_unity_bridge\src;%PYTHONPATH% && echo [Gateway Backend] && uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

REM Start Webapp (Vite)
set WEBAPP_TITLE=AGP Webapp
start "!WEBAPP_TITLE!" cmd /k "cd /d webapp && echo [Webapp] && npm run dev"

echo.
echo [dev_up] Started backend (8000) and webapp (5173). Press any key to exit this launcher.
pause > nul
popd
endlocal
