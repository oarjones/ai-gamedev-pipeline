@echo off
setlocal
chcp 65001 >nul

REM ============================================================
REM Install Blender Python deps from requirements-blender.txt
REM Usage:
REM   install_blender_deps.bat [ruta\blender.exe] [ruta\requirements.txt]
REM ============================================================

REM --- 1) Resolver blender.exe ---
if "%~1"=="" (
  if exist "C:\Program Files\Blender Foundation\Blender 4.5\blender.exe" (
    set "BLENDER_EXE=C:\Program Files\Blender Foundation\Blender 4.5\blender.exe"
  ) else (
    echo [ERROR] No se encontro blender.exe. Pasa la ruta como primer argumento.
    exit /b 1
  )
) else (
  set "BLENDER_EXE=%~1"
)

REM --- 2) Resolver requirements ---
if "%~2"=="" (
  set "SCRIPT_DIR=%~dp0"
  if exist "%SCRIPT_DIR%requirements-blender.txt" (
    set "REQ_FILE=%SCRIPT_DIR%requirements-blender.txt"
  ) else if exist "%SCRIPT_DIR%..\mcp_blender_addon\requirements-blender.txt" (
    set "REQ_FILE=%SCRIPT_DIR%..\mcp_blender_addon\requirements-blender.txt"
  ) else (
    echo [ERROR] No se encontro requirements-blender.txt. Pasa la ruta como segundo argumento.
    exit /b 1
  )
) else (
  set "REQ_FILE=%~2"
)

echo.
echo Blender exe: "%BLENDER_EXE%"
echo Reqs file  : "%REQ_FILE%"
echo.

if not exist "%BLENDER_EXE%" (
  echo [ERROR] blender.exe no existe en "%BLENDER_EXE%"
  exit /b 1
)
if not exist "%REQ_FILE%" (
  echo [ERROR] requirements-blender.txt no existe en "%REQ_FILE%"
  exit /b 1
)

REM --- 3) Obtener Python embebido (sin FOR, usando fichero temporal) ---
set "TMP_BPY=%TEMP%\bpy_path_%RANDOM%.txt"
"%BLENDER_EXE%" -b --python-expr "import sys;print(sys.executable)" > "%TMP_BPY%" 2>nul
set /p BPY=<"%TMP_BPY%"
del "%TMP_BPY%" >nul 2>&1

if not defined BPY (
  echo [ERROR] No se pudo determinar el ejecutable de Python de Blender.
  exit /b 1
)

echo Blender Python: "%BPY%"

REM --- 4) Herramientas de pip ---
"%BPY%" -m ensurepip --upgrade
"%BPY%" -m pip install --upgrade pip setuptools wheel || (
  echo [ERROR] No se pudo actualizar pip/setuptools/wheel.
  echo        Prueba ejecutar este .bat como Administrador.
  exit /b 1
)

REM --- 5) Instalar dependencias ---
echo.
echo Instalando dependencias desde requirements...
"%BPY%" -m pip install -r "%REQ_FILE%"
if errorlevel 1 (
  echo.
  echo [ERROR] Fallo instalando dependencias en el Python de Blender.
  echo        Alternativa por-usuario (sin admin), ejemplo:
  echo        "%BPY%" -m pip install --target "%%APPDATA%%\Blender Foundation\Blender\4.5\scripts\modules" -r "%REQ_FILE%"
  exit /b 1
)

REM --- 6) Verificacion rapida ---
echo.
"%BPY%" -c "import sys; print('Python:', sys.version)"
"%BPY%" -c "import PIL; import importlib; print('Pillow:', getattr(PIL,'__version__','OK'))" 2>nul || echo Pillow: NO
"%BPY%" -c "import numpy, importlib; print('numpy:', numpy.__version__)" 2>nul || echo numpy: NO
"%BPY%" -c "import websockets, importlib; print('websockets:', websockets.__version__)" 2>nul || echo websockets: NO

echo.
echo [OK] Dependencias instaladas correctamente en el entorno de Python de Blender.
exit /b 0
