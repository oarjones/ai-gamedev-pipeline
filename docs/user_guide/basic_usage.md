# Uso básico

1. Inicia el MCP Bridge.
2. Abre el proyecto Unity y espera la conexión.
3. Abre Blender con el addon activado.
4. Ejecuta un comando de prueba desde Unity (p. ej., crear un objeto en Blender) o desde Blender (generar malla).

## Flujo típico

1. Unity emite un comando (JSON) → Bridge.
2. Bridge valida y delega → Blender Addon.
3. Blender ejecuta, responde → Bridge → Unity.

