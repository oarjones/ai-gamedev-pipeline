# Configuración de MCP Bridge (Python)

El Bridge expone servicios WebSocket/HTTP para conectar Unity y Blender con herramientas MCP.

## Instalación

```bash
python -m venv .venv
.venv\\Scripts\\activate  # Windows
pip install -r mcp_unity_bridge/requirements.txt
pip install -r mcp_unity_bridge/requirements-agent.txt  # opcional
```

## Ejecución

```bash
python mcp_unity_bridge/src/mcp_unity_server/main.py
```

O usa `mcp_unity_bridge/launch.bat` si está disponible.

## Configuración

- Edita `mcp_unity_bridge/src/mcp_unity_server/config.py` para puertos, rutas y seguridad.
- Variables de entorno recomendadas (si aplica): `MCP_HOST`, `MCP_PORT`.

## Verificación

1. Inicia el Bridge y revisa logs de arranque.
2. Con Unity abierto, verifica handshake en consola.
3. Desde Blender, ejecuta un comando simple (p. ej., crear cubo) y confirma respuesta.

