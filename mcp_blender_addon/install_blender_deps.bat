@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

REM ============================================================
REM  Install Blender Python deps from requirements-blender.txt
REM  Usage:
REM    install_blender_deps.bat [ruta\blender.exe] [ruta\requirements.txt]
REM
REM  Si no pasas argumentos, intenta autodetectar blender.exe y
REM  busca requirements-blender.txt cerca del script.
REM ============================================================

REM --- 1) Resolver blender.exe ---
set "BLENDER_EXE="
if not "%~1"=="" (
  set "BLENDER_EXE=%~1"
)

if not defined BLENDER_EXE (
  REM Ruta típica (Blender 4.5)
  if exist "C:\Program Files\Blender Foundation\Blender 4.5\blender.exe" set "BLENDER_EXE=C:\Program Files\Blender Foundation\Blender 4.5\blender.exe"
)

if not defined BLENDER_EXE (
  REM Ruta genérica (última instalada en esa carpeta)
  if exist "C:\Program Files\Blender Foundation\Blender\blender.exe" set "BLENDER_EXE=C:\Program Files\Blender Foundation\Blender\blender.exe"
)

if not defined BLENDER_EXE (
  REM Si blender está en PATH
  for /f "delims=" %%B in ('where blender 2^>nul') do (
    set "BLENDER_EXE=%%B"
    goto :found_blender
  )
)

:found_blender
if not defined BLENDER_EXE (
  echo [ERROR] No se ha podido localizar blender.exe
  echo         Pasa la ruta como primer argumento, p. ej.:
  echo         scripts\install_blender_deps.bat "C:\Program Files\Blender Foundation\Blender 4.5\blender.exe"
  exit /b 1
)

REM --- 2) Resolver requirements.txt ---
set "SCRIPT_DIR=%~dp0"
set "REQ_FILE="

if not "%~2"=="" (
  set "REQ_FILE=%~2"
) else (
  REM Busca primero junto al script
  if exist "%SCRIPT_DIR%requirements-blender.txt" set "REQ_FILE=%SCRIPT_DIR%requirements-blender.txt"
  REM Luego en mcp_blender_addon\
  if not defined REQ_FILE if exist "%SCRIPT_DIR%..\mcp_blender_addon\requirements-blender.txt" set "REQ_FILE=%SCRIPT_DIR%..\mcp_blender_addon\requirements-blender.txt"
  REM Por último en la raíz del repo
  if not defined REQ_FILE if exist "%SCRIPT_DIR%..\requirements-blender.txt" set "REQ_FILE=%SCRIPT_DIR%..\requirements-blender.txt"
)

if not defined REQ_FILE (
  echo [ERROR] No se encuentra requirements-blender.txt
  echo         Pasa la ruta como segundo argumento o copia el archivo junto al .bat
  exit /b 1
)

echo.
echo Blender exe: "%BLENDER_EXE%"
echo Reqs file  : "%REQ_FILE%"
echo.

REM --- 3) Obtener el Python embebido de Blender ---
set "BPY="
for /f "usebackq delims=" %%P in (`"%BLENDER_EXE%" -b --python-expr "import sys;print(sys.executable)"`) do (
  set "BPY=%%P"
)

if not defined BPY (
  echo [ERROR] No se pudo obtener el ejecutable de Python de Blender.
  exit /b 1
)

echo Blender Python: "%BPY%"

REM --- 4) ensurepip / upgrade pip toolchain ---
"%BPY%" -m ensurepip --upgrade || (
  echo [WARN ] ensurepip fallo; continuando...
)
"%BPY%" -m pip install --upgrade pip setuptools wheel || (
  echo [ERROR] No se pudo actualizar pip/setuptools/wheel.
  echo         Prueba ejecutando esta ventana como Administrador.
  exit /b 1
)

REM --- 5) Instalar dependencias ---
echo.
echo Instalando dependencias desde requirements...
"%BPY%" -m pip install -r "%REQ_FILE%"
if errorlevel 1 (
  echo.
  echo [ERROR] Fallo instalando dependencias en el Python de Blender.
  echo         Si ves errores de permisos, vuelve a ejecutar este .bat como Administrador.
  echo         Alternativa: instala en la carpeta de usuario:
  echo         "%BPY%" -m pip install --target "%%APPDATA%%\Blender Foundation\Blender\4.5\scripts\modules" -r "%REQ_FILE%"
  exit /b 1
)

REM --- 6) Mostrar version de Python y paquetes clave (opcional) ---
echo.
"%BPY%" - <<PYCODE
import sys, pkgutil
print("Python:", sys.version)
for mod in ("Pillow","numpy","websockets"):
    try:
        __import__(mod)
        print(f"{mod}: OK")
    except Exception as e:
        print(f"{mod}: NO ({e})")
PYCODE

echo.
echo [OK] Dependencias instaladas correctamente en el entorno de Python de Blender.
exit /b 0
