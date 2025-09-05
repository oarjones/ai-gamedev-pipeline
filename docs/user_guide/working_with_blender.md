# Trabajo con Blender

- `commands/` contiene operaciones agrupadas (modeling, topology, scene, etc.).
- `server/` gestiona ejecución, validación y registro de comandos invocados.

## Ejemplo

```python
# En Blender Python Console (conceptual)
from mcp_blender_addon.commands import modeling
modeling.create_cube(size=2.0)
```

Consulta `API > Comandos Blender` para la referencia detallada.

