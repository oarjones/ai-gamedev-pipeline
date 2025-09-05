# Depuración

## Logs

- Bridge: `mcp_unity_bridge/src/logging_system/*`.
- Unity: Consola del Editor y logs del `MCPLogger`.
- Blender: consola de Blender y registro del addon.

## Estrategia

- Reproduce con `requestId` y correlaciona en los tres lados.
- Activa niveles `DEBUG` temporalmente para diagnóstico.
- Aísla reproducciones: comandos mínimos y entradas deterministas.

