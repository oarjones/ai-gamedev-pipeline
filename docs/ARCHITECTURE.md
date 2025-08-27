# Arquitectura

El proyecto se organiza en tres componentes principales que permiten a un agente de IA controlar distintas aplicaciones de desarrollo de videojuegos:

## Adaptador unificado

- Expone las herramientas del proyecto mediante el protocolo MCP.
- Actúa como fachada entre el agente de IA y los distintos bridges.
- Se ejecuta con `python mcp_unity_bridge/mcp_adapter.py` y enruta las peticiones a los servicios disponibles.

## Unity Bridge

- Servidor FastAPI que mantiene un canal WebSocket con el editor de Unity.
- Traduce las peticiones del adaptador en comandos o consultas C# para Unity.
- Se lanza con `python -m mcp_unity_server.main` desde el directorio `mcp_unity_bridge`.

## Blender Bridge

- Add-on de Blender con un pequeño servidor WebSocket.
- Permite que el adaptador invoque acciones sobre Blender mediante Python (`bpy`).
- Puede iniciarse con Blender en modo consola: `blender --background --python mcp_blender_bridge/mcp_blender_addon/websocket_server.py`.

Estos tres procesos conforman el stack mínimo para que el agente de IA interactúe con los editores.
