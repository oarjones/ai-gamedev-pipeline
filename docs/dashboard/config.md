---
title: Configuración del Dashboard
---

# Configuración del Dashboard

## Config global
Archivo `config/settings.yaml`:
- `gateway.server`: host/port/reload
- `gateway.cors`: orígenes permitidos
- `servers`: endpoints de `mcp_bridge`, `unity_editor`, `blender_addon`
- `paths`: rutas (e.g., `unity_project`)
- `timeouts`: por servicio
- `gateway.config`: configuración centralizada (nueva)

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
    "args": ["-u", "-m", "mcp_unity_bridge.mcp_adapter"],
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

## Notas
- El `MCPClient` recoge `agent.env` por proyecto para apuntar a los endpoints correctos.
- Cambiar `agent.adapter` modifica cómo se interpretan líneas del agente sin tocar otros servicios.

## Endpoints de Config
- `GET /api/v1/config` — retorna configuración actual (keys enmascaradas)
- `POST /api/v1/config` — persiste cambios tras validar (rutas, puertos libres, formato de keys). Guarda backup `settings.yaml.bak` y escritura atómica.
