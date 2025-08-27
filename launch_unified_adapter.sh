#!/usr/bin/env bash
# Inicia Unity Bridge, Blender Bridge y el adaptador MCP unificado.
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

# Asegurar que el servidor de Unity pueda importarse
export PYTHONPATH="$ROOT_DIR/mcp_unity_bridge/src:$PYTHONPATH"

# Lanzar Unity Bridge en segundo plano
python -m mcp_unity_server.main &
UNITY_PID=$!

echo "Unity Bridge iniciado (PID $UNITY_PID)"

# Lanzar Blender Bridge (requiere 'blender' en el PATH)
blender --background --python mcp_blender_bridge/mcp_blender_addon/websocket_server.py &
BLENDER_PID=$!

echo "Blender Bridge iniciado (PID $BLENDER_PID)"

# Lanzar el adaptador unificado en primer plano
python mcp_unity_bridge/mcp_adapter.py

# Al salir, detener los bridges
kill $UNITY_PID $BLENDER_PID 2>/dev/null || true
