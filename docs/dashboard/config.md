---
title: ConfiguraciÃ³n del Dashboard
---

# ConfiguraciÃ³n del Dashboard

## Config global
Archivo `config/settings.yaml`:
- `gateway.server`: host/port/reload
- `gateway.cors`: orÃ­genes permitidos
- `servers`: endpoints de `mcp_bridge`, `unity_editor`, `blender_addon`
- `paths`: rutas (e.g., `unity_project`)
- `timeouts`: por servicio
- `agent.mcp.adapterOwnership`: control de propiedad del MCP Adapter (`agent_runner_only` por defecto). Si estÃ¡ activo, el `AgentRunner` lanza y detiene el adapter, garantizando instancia Ãºnica via lockfile.
- `gateway.config`: configuraciÃ³n centralizada (nueva)

Ejemplo `gateway.config`:

```yaml
gateway:
  config:
    version: "1.0"
    executables:
      unityExecutablePath: "C:\\Program Files\\Unity\\Hub\\Editor\\...\\Unity.exe"
      blenderExecutablePath: "C:\\Program Files\\Blender Foundation\\Blender 4.1\\blender.exe"
      unityProjectRoot: "projects"
    bridges:
      unityBridgePort: 8001
      blenderBridgePort: 8002
    integrations:
      gemini: { apiKey: "****", defaultModel: "" }
      openai: { apiKey: "****", defaultModel: "gpt-4o" }
      anthropic: { apiKey: "****", defaultModel: "claude-3-sonnet-20240229" }
    projects: { root: "projects" }
```

Notas:
- Las API keys se enmascaran en las respuestas y en la UI (`****abcd`). Para actualizarlas, escribe el valor completo y guarda.
- Se mantiene compatibilidad con `servers`, `paths` y `gateway.processes` actuales. Si no hay valores en `gateway.config`, se rellenan a partir de esas secciones.

## Config por proyecto
Archivo `projects/<id>/.agp/project.json`:

```json
{
  "id": "<id>",
  "name": "<name>",
  "settings": { "default_context_path": "context" },
  "agent": {
    "adapter": "cli_generic",
    "executable": "python",
    "args": ["-u", "-m", "bridges.mcp_adapter"],
    "env": {
      "MCP_SERVER_URL": "ws://127.0.0.1:8001/ws/gemini_cli_adapter",
      "BLENDER_SERVER_URL": "ws://127.0.0.1:8002"
    },
    "default_timeout": 5.0,
    "terminate_grace": 3.0
  }
}
```

- `agent.adapter`: estrategia de parseo/formateo (`cli_generic`, extensible)
- `agent.executable/args`: binario del agente y argumentos
- `agent.env`: variables para MCP/LLM
- Tiempos: afectan a `AgentRunner.send()` y parada
 - Cuando `agent.mcp.adapterOwnership` es `agent_runner_only`, no arranques el adapter desde scripts externos; el `AgentRunner` lo harÃ¡ como `python -u -m bridges.mcp_adapter` usando los puertos configurados.

## Notas
- El `MCPClient` recoge `agent.env` por proyecto para apuntar a los endpoints correctos.
- Cambiar `agent.adapter` modifica cÃ³mo se interpretan lÃ­neas del agente sin tocar otros servicios.

## Endpoints de Config
- `GET /api/v1/config` â€” retorna configuraciÃ³n actual (keys enmascaradas)
- `POST /api/v1/config` â€” persiste cambios tras validar (rutas, puertos libres, formato de keys). Guarda backup `settings.yaml.bak` y escritura atÃ³mica.

