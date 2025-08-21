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