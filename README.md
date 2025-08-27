# AI GameDev Pipeline

Este repositorio contiene el proyecto para construir una pipeline de desarrollo de videojuegos completamente automatizada y dirigida por un agente de IA.

## Visión del Proyecto

El objetivo es crear un ecosistema donde un agente de IA pueda orquestar un flujo de trabajo completo a través de múltiples aplicaciones de software (Unity, Blender, etc.) para facilitar y acelerar la creación de videojuegos. La meta es permitir que el desarrollador se centre en las mecánicas y la visión creativa, mientras que la IA se encarga de la implementación técnica.

## Arquitectura Planificada

El sistema se basará en una arquitectura de microservicios, con un "puente" (servidor MCP) para cada aplicación de software:

- **`mcp_unity_bridge`**: Un servidor en Python que se comunica con el editor de Unity para ejecutar scripts de C#, manipular escenas y gestionar los assets del proyecto.
- **`mcp_blender_bridge`**: Un servidor en Python que se comunica con Blender para ejecutar scripts de Python (`bpy`), permitiendo el modelado 3D, texturizado y animación de forma programática.

## Estado Actual

Proyecto en fase de inicialización. El primer objetivo es implementar el `mcp_unity_bridge`.

## Ejemplos de ejecución

### Unity Bridge
```sh
python -m mcp_unity_server.main
```

### Blender Bridge
```sh
blender --background --python mcp_blender_bridge/mcp_blender_addon/websocket_server.py
```

### Instalación para Blender 2.79

Blender 2.79 incluye Python 3.5. Para ejecutar el servidor WebSocket debes
instalar la versión compatible de la librería `websockets` dentro del entorno
de Blender:

1. Descarga [Blender&nbsp;2.79](https://download.blender.org/release/Blender2.79/).
2. Abre una terminal en la carpeta de Blender y prepara `pip`:
   ```sh
   ./2.79/python/bin/python3.5 -m ensurepip
   ./2.79/python/bin/pip install websockets==7.0
   ```
3. Desde la raíz de este repositorio ejecuta:
   ```sh
   blender --background --python mcp_blender_bridge/mcp_blender_addon/websocket_server.py
   ```

Si `blender` no está en el `PATH` usa la ruta completa al ejecutable.
La única dependencia externa es `websockets==7.0`, necesaria porque las
versiones más recientes requieren Python&nbsp;3.7 o superior.

### Adaptador unificado
```sh
python mcp_unity_bridge/mcp_adapter.py
```

También puedes lanzar todo el stack con:
```sh
./launch_unified_adapter.sh
```
 o en Windows:
```bat
launch_unified_adapter.bat
```

