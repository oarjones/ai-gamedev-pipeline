# Visión y Arquitectura del Proyecto: AI GameDev Pipeline

## 1. Visión del Proyecto

El objetivo de **AI GameDev Pipeline** es construir un ecosistema de desarrollo de videojuegos donde un agente de Inteligencia Artificial actúe como un desarrollador técnico autónomo. Este sistema permitirá al director creativo o diseñador de juegos centrarse en las mecánicas, la narrativa y la visión artística, delegando la implementación técnica de la creación de assets y la programación de la lógica del juego a la IA.

En esencia, se trata de crear una **pipeline de creación de contenido totalmente automatizada y dirigida por IA**, desde el modelado 3D inicial hasta la implementación final en el motor de juego.

## 2. Alcance y Objetivos Clave

El sistema final deberá ser capaz de realizar las siguientes tareas de forma autónoma, a partir de instrucciones en lenguaje natural y referencias visuales:

* **Modelado y Texturizado 3D:** Crear, modificar y texturizar modelos 3D utilizando Blender, basándose en descripciones textuales e imágenes de referencia.
* **Gestión de Assets:** Exportar los assets creados desde Blender e importarlos correctamente en un proyecto de Unity.
* **Implementación en el Motor de Juego:** Configurar los assets importados en Unity (crear Prefabs, asignar materiales) y manipular las escenas del juego.
* **Generación de Código:** Escribir, modificar y depurar scripts de C# en Unity para implementar la lógica del juego.
* **Bucle de Feedback Visual:** El agente de IA deberá ser capaz de solicitar y analizar capturas de pantalla de los editores (Blender, Unity) para verificar el estado de su trabajo, corregir errores y tomar decisiones basadas en el contexto visual actual.

## 3. Análisis Técnico y Tecnologías

La viabilidad del proyecto se apoya en la sinergia de varias tecnologías clave:

* **Agente IA (Gemini):** Será el "cerebro" del sistema. Se aprovecharán sus capacidades multimodales (comprensión de texto e imágenes) y su habilidad para usar herramientas (`tool use`) para planificar tareas complejas y generar el código necesario.
* **Servidores MCP (Python/FastAPI):** Actuarán como el "sistema nervioso", traduciendo las peticiones de la IA en acciones concretas. Su naturaleza ligera y la facilidad para crear APIs robustas los hacen ideales como puentes de comunicación.
* **Unity (C#):** La manipulación del editor se logrará mediante la ejecución dinámica de código C# a través de `Microsoft.CSharp.CSharpCodeProvider`. Un servidor HTTP integrado en el editor recibirá estos comandos.
* **Blender (Python API):** La automatización de Blender es muy directa gracias a su potente y nativa API de scripting en Python (`bpy`). El MCP de Blender ejecutará scripts `bpy` para realizar las tareas de modelado y animación.

## 4. Arquitectura del Sistema

El proyecto se basa en una **arquitectura de microservicios desacoplada**, donde cada componente tiene una única responsabilidad.

* **El Agente IA:** Es el orquestador. Recibe el objetivo de alto nivel y lo descompone en un plan de acción, decidiendo qué herramienta (MCP de Unity o MCP de Blender) usar en cada paso.
* **MCP Unity Bridge:** Un servidor FastAPI que expone la funcionalidad del editor de Unity a la IA. Su única misión es recibir comandos, pasárselos a Unity y devolver el resultado.
* **MCP Blender Bridge:** Un servidor FastAPI que expone la funcionalidad de Blender. Su única misión es recibir scripts `bpy`, pasárselos a Blender y devolver el resultado.
* **Servidores Internos (Unity/Blender):** Ligeros servidores HTTP que se ejecutan dentro de las aplicaciones principales para recibir y ejecutar los comandos enviados por los puentes MCP.

!

[Image of a microservices architecture diagram]
(httpsa://storage.googleapis.com/gemini-prod/images/2024/5/20/d1c08d0e-909d-4394-817f-474d284e3e35.png)

**Flujo de Ejemplo (Crear e Importar un Personaje):**
1.  **Usuario a IA:** "Crea un personaje robot simple basado en esta imagen y ponlo en la escena principal de Unity."
2.  **IA a MCP Blender:** Envía una secuencia de comandos `bpy` para modelar el robot.
3.  **IA a MCP Blender:** Envía un comando para exportar el modelo como `robot.fbx` a una ruta compartida.
4.  **IA a MCP Unity:** Envía un comando para que Unity actualice su base de datos de assets y detecte el nuevo archivo `robot.fbx`.
5.  **IA a MCP Unity:** Envía comandos para crear un Prefab a partir del modelo importado.
6.  **IA a MCP Unity:** Envía un comando para instanciar el Prefab en la escena activa.
7.  **IA a MCP Unity:** Pide una captura de pantalla (`TAKE_SCREENSHOT`) para verificar visualmente que el robot está en la escena.

## 5. Estructura del Repositorio

El proyecto se organizará en un monorepo con la siguiente estructura para mantener los componentes separados pero cohesionados:

```
ai-gamedev-pipeline/
├── docs/
│   └── PROJECT_VISION.md
│
├── mcp_unity_bridge/
│   ├── src/mcp_unity_server/
│   └── tests/
│
├── mcp_blender_bridge/
│   ├── src/mcp_blender_server/
│   └── tests/
│
├── unity_project/
│   └── Assets/
│       └── Editor/
│           └── MCP/
│
├── blender_addons/
│   └── mcp_addon/
│
└── README.md
```