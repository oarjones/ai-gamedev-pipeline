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

### Flujo de exportación de assets

- El comando `export_fbx(path)` envía a Blender la orden de exportar la escena actual en formato FBX.
- Los archivos generados se guardan en `unity_project/Assets/Generated/`, carpeta compartida con Unity para que el editor detecte los nuevos assets.

Estos tres procesos conforman el stack mínimo para que el agente de IA interactúe con los editores.

## Ejecución remota en Blender

El servidor WebSocket del add-on de Blender expone comandos para ejecutar código Python dentro de la escena en curso.

### `execute_python` y `execute_python_file`

- `execute_python` evalúa un bloque de código enviado desde el cliente.
- `execute_python_file` carga y ejecuta un archivo de script ubicado en la máquina donde corre Blender.

### Macros

Los macros son módulos almacenados en `mcp_blender_addon/macros` que definen una función `run(**kwargs)`.
El comando `run_macro` importa el módulo solicitado y ejecuta dicha función.

Ejemplo de petición:

```json
{"command": "run_macro", "params": {"name": "assign_material", "object_name": "Cube", "material_name": "Demo"}}
```

### Seguridad

Tanto la ejecución de código como los macros pueden ejecutar instrucciones arbitrarias con los permisos del usuario que
corre Blender. Sólo deben utilizarse con scripts de confianza y en entornos controlados.
