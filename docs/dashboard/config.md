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

