# Visión del Proyecto: AI GameDev Pipeline

## 1. Resumen Ejecutivo

Este documento describe la visión a corto, medio y largo plazo para el proyecto **AI GameDev Pipeline**, un sistema diseñado para revolucionar el flujo de trabajo en el desarrollo de videojuegos mediante la orquestación de tareas complejas a través de un agente de Inteligencia Artificial (IA).

El objetivo fundamental es **liberar al desarrollador de la carga técnica de la implementación**, permitiéndole centrarse en la creatividad, el diseño de mecánicas y la supervisión del producto. El sistema evolucionará desde un puente de comandos para Unity hasta un ecosistema multi-aplicación totalmente autónomo, culminando en un verdadero **"Director Técnico Artificial"**.

---

## 2. Fase 1: El Producto Mínimo Viable (MVP) - El Puente con Unity

La fase actual del proyecto se centra en construir el "motor y el chasis" del sistema: un puente de comunicación robusto entre el agente de IA y el editor de Unity.

* **Arquitectura:** Un servidor intermedio (MCP - Master Control Program) basado en FastAPI actúa como traductor, recibiendo comandos del agente IA y enviándolos a un servidor HTTP dentro de Unity para su ejecución.
* **Funcionalidad Central:**
    * **Ejecución de Código C#:** El agente puede enviar fragmentos de código C# para ser compilados y ejecutados dinámicamente en el editor de Unity.
    * **Gestión de Dependencias:** El sistema es capaz de manejar `usings` y referencias a ensamblados adicionales de forma dinámica, permitiendo la ejecución de código complejo.
    * **Comunicación Unidireccional:** El flujo principal es IA -> MCP -> Unity, donde la IA "habla" y Unity "ejecuta".

Esta base funcional es el cimiento indispensable sobre el que se construirán todas las capacidades futuras. Es el primer paso para demostrar la viabilidad del concepto.

---

## 3. Fase 2: Hoja de Ruta Post-MVP - La Evolución del Agente en Unity

Una vez que el MVP sea estable, el siguiente paso es dotar a la IA de capacidades que le permitan pasar de ser un simple ejecutor de código a un asistente inteligente y consciente de su entorno.

### Módulo 5: Conciencia del Entorno (La IA Aprende a "Ver" y "Leer")

La comunicación debe ser bidireccional. La IA necesita herramientas para consultar y entender el estado actual del proyecto de Unity.

* **Nuevas Herramientas MCP Sugeridas:**
    * `unity.getSceneHierarchy()`: Devuelve un árbol JSON de los GameObjects en la escena, permitiendo a la IA entender la estructura espacial.
    * `unity.getGameObjectDetails(id)`: Proporciona una lista detallada de los componentes, propiedades y valores de un objeto específico.
    * `unity.getProjectFiles(path)`: Permite a la IA navegar por el sistema de archivos del proyecto (`Assets`).
    * `unity.findAsset(query)`: Una función de búsqueda más abstracta para localizar prefabs, materiales o scripts por nombre o tipo.
* **Impacto:** La IA podrá tomar decisiones informadas, como "antes de crear un script de `PlayerController`, voy a comprobar si ya existe uno en el proyecto".

### Módulo 6: Seguridad y Sandboxing (Estableciendo Límites)

Con un gran poder viene una gran responsabilidad. Es crucial limitar el alcance de la IA para prevenir acciones destructivas, ya sean intencionadas o accidentales.

* **Implementación:**
    * **Análisis de Código Estático:** El MCP analizará el código C# entrante para detectar patrones peligrosos (ej. `File.Delete`, `Application.Quit`, llamadas de red) y los bloqueará.
    * **Sistema de Permisos:** Para acciones críticas (modificar `ProjectSettings`, eliminar múltiples archivos), la IA podría tener que solicitar un permiso explícito que el desarrollador humano debe aprobar.

### Módulo 7: Comunicación en Tiempo Real (La Línea Directa)

El modelo HTTP de petición-respuesta es robusto pero lento. Para una interacción fluida, se necesita una conexión persistente.

* **Tecnología Propuesta:** Implementar **WebSockets** entre el MCP y Unity.
* **Impacto Revolucionario:**
    * **Streaming de la Consola:** Unity podría enviar logs (`Debug.Log`, errores, warnings) al MCP en tiempo real. La IA podría "observar" la consola mientras se ejecuta un script y depurar problemas sobre la marcha.
    * **Notificaciones de Estado:** Unity podría notificar a la IA sobre eventos del editor, como "el usuario ha seleccionado un nuevo objeto" o "la compilación de scripts ha finalizado".

### Módulo 8: Herramientas de Alto Nivel (Abstracción y Eficiencia)

En lugar de que la IA escriba siempre código de bajo nivel, se pueden crear "macros" o herramientas abstractas en el MCP para tareas comunes.

* **Ejemplo:** Un endpoint `/tools/createCharacterController`.
    * **IA envía (JSON):** `{"name": "Player", "capsuleHeight": 2, "movementSpeed": 5.0, "includeRigidbody": true}`
    * **MCP traduce y envía a Unity (C#):** La secuencia de 5-10 comandos C# necesarios para crear el GameObject, añadir los componentes `CharacterController` y `Rigidbody`, configurar sus propiedades y crear un script básico de movimiento.
* **Beneficio:** Acelera drásticamente el desarrollo de tareas repetitivas y reduce la probabilidad de errores en el código generado por la IA.

---

## 4. Fase 3: El Ecosistema Multi-Aplicación (Integración con Blender)

Esta fase expande la visión más allá de Unity, creando una **pipeline de creación de contenido totalmente automatizada**.

* **La Pieza Clave: Un MCP para Blender:**
    * Crear un segundo servidor MCP que se comunique con Blender.
    * **Ventaja Estratégica:** Blender tiene una potentísima API de scripting en **Python (`bpy`)**, lo que facilita enormemente la integración. La IA podría generar scripts de Python que Blender ejecutaría de forma nativa.
* **El Agente "Director de Orquesta":**
    * El agente IA central ahora gestiona tareas que abarcan múltiples aplicaciones.
    * **Ejemplo de Flujo de Trabajo (Golem de Roca):**
        1.  **IA a MCP-Blender:** "Ejecuta este script de Python para generar un modelo 3D de un golem de roca, crea una animación de muerte y exporta todo como `golem.fbx` a la ruta `.../UnityProject/Assets/Models`."
        2.  **IA a MCP-Unity:** "He creado un nuevo archivo en `Assets/Models/golem.fbx`. Importa este modelo, crea un prefab a partir de él, añade un `Rigidbody` y un `BoxCollider`."
        3.  **IA a MCP-Unity:** "Ahora, crea un nuevo script C# llamado `GolemHealth.cs` con esta lógica..."

Este sistema elimina la fricción manual entre la creación de assets y su implementación en el motor de juego, representando un ahorro de tiempo monumental.

---

## 5. Fase 4: El Agente Consciente - El Bucle de Feedback Visual

Esta es la evolución final y más transformadora: dotar a la IA de **percepción visual**. Esto convierte al sistema de un ejecutor de instrucciones a un agente autónomo y con capacidad de autocorrección.

* **Mecanismo Técnico:**
    * Crear herramientas en los MCP de Unity y Blender para **tomar capturas de pantalla** del viewport o de la ventana de juego.
    * Estas capturas se codifican en Base64 y se devuelven al agente IA como respuesta a un comando.
* **El Bucle de Percepción-Acción:**
    1.  **ACCIÓN:** La IA envía un comando (ej. "Crea una esfera roja en la posición X").
    2.  **PERCEPCIÓN:** La IA solicita una captura de pantalla de la escena.
    3.  **ANÁLISIS:** La IA analiza la imagen recibida. "¿La esfera está ahí? ¿Está en la posición correcta? ¿Es del color correcto?".
    4.  **CORRECCIÓN/SIGUIENTE PASO:** Basándose en el análisis, la IA decide su siguiente acción (ej. "El comando falló, lo reintento de otra forma" o "Perfecto, ahora añadiré un componente de luz").

* **Capacidades Desbloqueadas:**
    * **Autocorrección y Depuración Visual:** La IA puede detectar y corregir sus propios errores visualmente. "El personaje atraviesa el suelo; debo ajustar su `Collider`".
    * **Comprensión del Contexto Artístico:** La IA puede tomar decisiones basadas en la composición, la iluminación y la estética. "He colocado los árboles, pero visualmente se ven muy repetitivos; voy a rotarlos y escalarlos aleatoriamente".
    * **Desarrollo Guiado por Objetivo Visual:** El desarrollador podría proporcionar una imagen de referencia (arte conceptual) y dar la instrucción: **"Haz que la escena se vea así"**. La IA trabajaría de forma iterativa, tomando capturas y ejecutando comandos hasta que la salida visual coincida con el objetivo.
    * **Modelado 3D Multimodal:** Combinando la integración con Blender y el feedback visual, la IA podría **modelar un objeto 3D a partir de bocetos 2D** (vistas frontal, lateral, etc.), usando las imágenes como referencia directa en el viewport de Blender.

---

## 6. Conclusión: La Visión Final

El proyecto **AI GameDev Pipeline** representa un cambio de paradigma. Siguiendo esta hoja de ruta, evolucionará desde un útil asistente de programación para Unity hasta un **agente director autónomo**, capaz de gestionar un pipeline de producción de assets completo y de operar con un entendimiento visual de su trabajo.

El objetivo final es crear un colaborador creativo y técnico que permita a los desarrolladores de juegos operar a un nivel de abstracción sin precedentes, enfocando su energía en lo que realmente importa: **diseñar experiencias de juego innovadoras.**