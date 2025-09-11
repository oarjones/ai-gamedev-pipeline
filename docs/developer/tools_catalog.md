---
title: Catálogo de Tools (MCP → Providers)
---

# Catálogo de Tools

Este documento describe cómo se construye y se entrega el catálogo de herramientas MCP a los providers (p. ej., Gemini CLI) para habilitar prompts y esquemas de function-calling.

## Fuente de verdad

- El origen único es `mcp_unity_bridge/mcp_adapter.py`.
- Se detectan funciones decoradas con `@mcp.tool()` como herramientas disponibles.
- La descripción se extrae del docstring (primera línea). Los ejemplos se infieren de líneas que comienzan con `Ejemplo:` o `Example:`.

## Construcción del catálogo

Componente: `gateway/app/services/tool_catalog.py`.

- Analiza el archivo del adapter con AST (no ejecución) y crea `ToolSpec` por función.
- Mapeo básico de tipos de parámetros a JSON Schema:
  - `str → {"type":"string"}`
  - `int → {"type":"integer"}`
  - `float → {"type":"number"}`
  - `bool → {"type":"boolean"}`
  - `dict → {"type":"object"}`
  - `list → {"type":"array"}`
  - otros/ausentes → tipo permisivo (`[string, number, boolean, object, array, null]`).
- Reglas de `required`: argumentos sin valor por defecto.
- Validación opcional de JSON Schema con `jsonschema` si está instalado.

### Artefactos generados

`build_catalog()` produce un dict con:

- `version`: hash abreviado del adapter (12 chars)
- `hash`: SHA-1 del archivo `mcp_adapter.py`
- `count`: número de tools
- `promptList`: texto human-readable (nombre + descripción + ejemplos)
- `functionSchema`: lista `[{ name, description, parameters }]`

## Caché

- Ubicación: `gateway/.cache/tool_catalog.json`.
- `get_catalog_cached()` devuelve el catálogo cacheado si el hash del adapter coincide; en caso contrario, reconstruye y sobrescribe.

## Entrega a Providers

- `AgentRunner` adjunta `toolCatalog` en `SessionCtx` al iniciar en modo provider (`provider='gemini_cli'`).
- Estructura entregada:

```json
{
  "version": "<12-char>",
  "hash": "<sha1>",
  "count": 42,
  "promptList": "- tool_a: desc...\n  e.g. ...",
  "functionSchema": [
    { "name": "unity_command", "description": "...", "parameters": { "type":"object", ... } },
    ...
  ]
}
```

## Buenas prácticas al definir tools

- Añade docstrings claros. La primera línea se usa como descripción.
- Incluye una o dos líneas de ejemplo precedidas por `Ejemplo:` / `Example:` para enriquecer `promptList`.
- Anota tipos de parámetros Python simples (`str`, `int`, `float`, `bool`, `list`, `dict`) cuando sea posible; ayudarán a generar JSON Schema más preciso.
- Mantén estable el nombre de la función; se usa como `name` del tool.

## Futuro

- Extender el mapeo de tipos (e.g., `Literal`, `Annotated`) y enriquecer validaciones.
- Soporte opcional de descriptor estático si el adapter no está disponible (no implementado aún).

