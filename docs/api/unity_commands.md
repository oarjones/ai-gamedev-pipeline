# Comandos Unity

Referencia de comandos disponibles en el Editor de Unity.

> Ejecuta `python scripts/generate_docs.py` para actualizar secciones autogeneradas.

## Índice

- `MCPWebSocketClient`
- `CommandDispatcher`
- `MCPToolbox`

## Detalle (autogenerado)

<!-- AUTO:UNITY_COMMANDS -->

## CSharpRunner

### (miembro)

Intenta compilar con referencias esenciales y reintenta con todas si falla.

### (miembro)

Compila el código con el conjunto de ensamblados proporcionado.

### BuildSourceTemplate

Envuelve el código del agente en una clase contenedora con método Run(). Devuelve el código final y el desplazamiento de línea para mapear errores.

### Execute

Compila y ejecuta el código C# proporcionado, devolviendo el resultado o errores.

**Parámetros:**
- `code`: Código fuente a ejecutar.
- `additionalReferences`: Lista de ensamblados adicionales por nombre o ruta.

## CommandDispatcher

### EnqueueAction

Encola una acción para ejecutarse en el ciclo de actualización del Editor.

### EnsureCameraAndLight

Garantiza la existencia de una cámara principal y una luz direccional.

### OnEditorUpdate

Drena la cola y ejecuta la siguiente acción, si existe.

### ProcessCommand

Ejecuta un comando de mutación (ImportFBX, EnsureCameraAndLight o código C# dinámico).

### ProcessIncomingMessage

Procesa un mensaje JSON entrante y emite la respuesta correspondiente.

**Parámetros:**
- `jsonData`: Mensaje en formato JSON.
### ProcessQuery

Resuelve consultas de solo lectura del entorno (jerarquía, screenshot, detalles, archivos).

### ProcessToolAction

Invoca un método público estático de <see cref="MCPToolbox"/> mapeándolo desde 'action'.


## CommandExecutionResult

### (miembro)

Clase genérica para envolver listas y objetos. Originalmente para JsonUtility, se mantiene por ahora para compatibilidad con EnvironmentScanner.


## DynamicExecutor

### GetAllAssemblies

Devuelve ubicaciones de todos los ensamblados cargados estáticamente más los esenciales.

### GetAssemblyLocation

Resuelve la ubicación de un ensamblado por nombre (sin extensión) o ruta.

### GetEssentialAssemblies

Conjunto mínimo de ensamblados comunes para la mayoría de scripts del Editor.

### SerializeReturnValue

Serializa el valor de retorno intentando usar JSON y con fallback a ToString().


## EnvironmentScanner

### (miembro)

(NUEVO MÉTODO) Extrae de forma segura las propiedades serializables de un componente de Unity. Extrae de forma segura propiedades serializables de un componente de Unity, filtrando tipos complejos y propiedades problemáticas.

### BuildGameObjectData

Construye recursivamente un árbol de GameObjectData para un GameObject dado.

### GetGameObjectDetails

Devuelve detalles serializados de un GameObject por InstanceID.

**Parámetros:**
- `instanceId`: Identificador de instancia de Unity.
### GetProjectFiles

Lista directorios y archivos (sin .meta) bajo Assets/ respetando seguridad de ruta.

**Parámetros:**
- `relativePath`: Ruta relativa bajo Assets/.
### GetSceneHierarchy

Serializa la jerarquía de la escena activa a un modelo ligero.

**Devuelve:** Wrapper con una lista de GameObjectData raíz.
### TakeScreenshot

Captura una imagen de la vista de escena o cámara principal en PNG base64.


## LogBuffer

### (miembro)

Crea un buffer con capacidad máxima configurable.

### Drain

Drena y devuelve las entradas encoladas en orden FIFO.

### Enqueue

Encola una entrada y trunca si excede la capacidad.


## LogWebSocketClient

### (miembro)

Construye el cliente apuntando a la URL del servidor de logs.

### (miembro)

Envía un mensaje JSON por WebSocket, gestionando reconexión y fallos.

### CanSend

Indica si se puede intentar enviar en este momento (no en cooldown).


## MCPLogger

### Configure

Configura nivel mínimo, componente y URL de WebSocket opcional para envío.

### Log

Registra un evento con nivel, mensaje y metadatos opcionales.

### LogPerformance

Registra una métrica de rendimiento con etiqueta y duración en ms.

### SetCategory

Establece una categoría opcional para agrupar eventos.


## MCPWebSocketClient

### Disconnect

Cierra la conexión WebSocket de forma ordenada al salir del Editor.

### Initialize

Inicializa el cliente y establece la conexión WebSocket. Se invoca en el primer ciclo del Editor tras cargar scripts.

### OnMessageReceived

Callback de recepción de mensajes desde el Bridge. Encola el procesamiento en el hilo del Editor.

### SendResponse

Envía una respuesta de Unity al Bridge por WebSocket.

**Parámetros:**
- `response`: Objeto con request_id, status y payload.

## ScreenshotData

### (miembro)

ContractResolver personalizado para ignorar propiedades que causan problemas con Unity.


## UnityMessage

### (miembro)

Modelo principal para las respuestas que se envían de vuelta al servidor MCP.


## ValidationError

### (miembro)

Human-readable message describing the issue.

### (miembro)

Optional 1-based line number where the issue occurs.

### (miembro)

Optional 1-based column number where the issue occurs.

### (miembro)

Severity classification for this finding.

### (miembro)

Optional code or identifier for the rule.

### (miembro)

Constructs a new instance.
<!-- AUTO:UNITY_COMMANDS:END -->
