---
title: CatÃ¡logo de Tools (MCP â†’ Providers)
---

# CatÃ¡logo de Tools

Este documento describe cÃ³mo se construye y se entrega el catÃ¡logo de herramientas MCP a los providers (p. ej., Gemini CLI) para habilitar prompts y esquemas de function-calling.

## Fuente de verdad

- El origen Ãºnico es `bridges/mcp_adapter.py`.
- Se detectan funciones decoradas con `@mcp.tool()` como herramientas disponibles.
- La descripciÃ³n se extrae del docstring (primera lÃ­nea). Los ejemplos se infieren de lÃ­neas que comienzan con `Ejemplo:` o `Example:`.

## ConstrucciÃ³n del catÃ¡logo

Componente: `gateway/app/services/tool_catalog.py`.

- Analiza el archivo del adapter con AST (no ejecuciÃ³n) y crea `ToolSpec` por funciÃ³n.
- Mapeo bÃ¡sico de tipos de parÃ¡metros a JSON Schema:
  - `str â†’ {"type":"string"}`
  - `int â†’ {"type":"integer"}`
  - `float â†’ {"type":"number"}`
  - `bool â†’ {"type":"boolean"}`
  - `dict â†’ {"type":"object"}`
  - `list â†’ {"type":"array"}`
  - otros/ausentes â†’ tipo permisivo (`[string, number, boolean, object, array, null]`).
- Reglas de `required`: argumentos sin valor por defecto.
- ValidaciÃ³n opcional de JSON Schema con `jsonschema` si estÃ¡ instalado.

### Artefactos generados

`build_catalog()` produce un dict con:

- `version`: hash abreviado del adapter (12 chars)
- `hash`: SHA-1 del archivo `mcp_adapter.py`
- `count`: nÃºmero de tools
- `promptList`: texto human-readable (nombre + descripciÃ³n + ejemplos)
- `functionSchema`: lista `[{ name, description, parameters }]`

## CachÃ©

- UbicaciÃ³n: `gateway/.cache/tool_catalog.json`.
- `get_catalog_cached()` devuelve el catÃ¡logo cacheado si el hash del adapter coincide; en caso contrario, reconstruye y sobrescribe.

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

## Buenas prÃ¡cticas al definir tools

- AÃ±ade docstrings claros. La primera lÃ­nea se usa como descripciÃ³n.
- Incluye una o dos lÃ­neas de ejemplo precedidas por `Ejemplo:` / `Example:` para enriquecer `promptList`.
- Anota tipos de parÃ¡metros Python simples (`str`, `int`, `float`, `bool`, `list`, `dict`) cuando sea posible; ayudarÃ¡n a generar JSON Schema mÃ¡s preciso.
- MantÃ©n estable el nombre de la funciÃ³n; se usa como `name` del tool.

## Futuro

- Extender el mapeo de tipos (e.g., `Literal`, `Annotated`) y enriquecer validaciones.
- Soporte opcional de descriptor estÃ¡tico si el adapter no estÃ¡ disponible (no implementado aÃºn).


