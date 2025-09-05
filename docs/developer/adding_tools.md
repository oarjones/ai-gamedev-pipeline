# Añadir herramientas

## Unity (C#)

1. Crea una clase en `Assets/Editor/MCP` o similar.
2. Documenta con XML comments y registra el comando en `MCPToolbox`/`CommandDispatcher`.
3. Asegura validación de parámetros y manejo de errores.

## Blender (Python)

1. Añade una función en `mcp_blender_addon/commands/` con docstring clara.
2. Registra la función en el `server/registry.py` (si aplica).
3. Añade tests mínimos en `mcp_blender_addon/tests/`.

## Bridge (Python)

1. Expón endpoints o handlers en `mcp_unity_server`.
2. Añade tipos en `models.py` y configuración en `config.py`.

