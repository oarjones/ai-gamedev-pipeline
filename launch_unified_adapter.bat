@echo off
REM Inicia Unity Bridge, Blender Bridge y el adaptador MCP unificado.
setlocal
cd /d "%~dp0"

REM Asegurar que el servidor de Unity pueda importarse
set "PYTHONPATH=%CD%\mcp_unity_bridge\src;%PYTHONPATH%"

REM Lanzar Unity Bridge en segundo plano
start "Unity Bridge" cmd /c "python -m mcp_unity_server.main"

REM Lanzar Blender Bridge (requiere 'blender' en el PATH)
start "Blender Bridge" cmd /c "blender --background --python mcp_blender_bridge\mcp_blender_addon\websocket_server.py"

REM Lanzar el adaptador unificado en primer plano
python mcp_unity_bridge\mcp_adapter.py

endlocal
