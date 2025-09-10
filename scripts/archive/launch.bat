@echo off
setlocal ENABLEDELAYEDEXPANSION

REM Ir a la carpeta del .bat (raíz del proyecto)
cd /d "%~dp0"

REM Activar el entorno virtual de la raíz
if exist ".venv\Scripts\activate.bat" (
  call ".venv\Scripts\activate.bat"
) else (
  echo [ADVERTENCIA] No se encontro "%CD%\.venv\Scripts\activate.bat"
)

REM Asegurar que 'src' esté en el PYTHONPATH (para resolver mcp_unity_server)
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"

REM Ejecutar la funcion main() que lanza uvicorn
python -m mcp_unity_server.main
set EXITCODE=%ERRORLEVEL%

if %EXITCODE% NEQ 0 (
  echo.
  echo [run_mcp_server] El servidor termino con codigo %EXITCODE%.
)

pause
endlocal & exit /b %EXITCODE%
