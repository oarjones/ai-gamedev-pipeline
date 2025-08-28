# mcp_adapter.py
import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict, Optional, Tuple

# SDK MCP (stdio por defecto)
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------
# Logging SIEMPRE a stderr (stdout queda limpio para el protocolo MCP)
# ---------------------------------------------------------------------
handler = logging.StreamHandler(sys.stderr)
logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
log = logging.getLogger("unity_mcp_adapter")

# ---------------------------------------------------------------------
# Instancia MCP: el nombre debe coincidir con settings.json (unity_editor)
# ---------------------------------------------------------------------
mcp = FastMCP("unity_editor")

# ---------------------------------------------------------------------
# URL del puente Unity (puedes sobreescribir con la variable de entorno)
# ---------------------------------------------------------------------
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "ws://127.0.0.1:8001/ws/gemini_cli_adapter")

# ---------------------------------------------------------------------
# Configuración del puente Blender y rutas compartidas
# ---------------------------------------------------------------------
BLENDER_SERVER_URL = os.getenv("BLENDER_SERVER_URL", "ws://127.0.0.1:8002")
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
UNITY_PROJECT_DIR = os.path.join(BASE_DIR, "unity_project")


async def send_to_unity_and_get_response(message: Dict[str, Any]) -> Dict[str, Any]:
    """
    Conecta con el WebSocket de Unity, envía 'message' y devuelve la respuesta como dict.
    - Lazy import de 'websockets' para que el server no caiga si falta el paquete.
    - NUNCA imprime en stdout.
    - Si la respuesta no es JSON válido, la devuelve como texto en 'payload'.
    """
    try:
        import websockets  # type: ignore
    except Exception as e:
        log.error("Falta el paquete 'websockets' en el entorno actual: %s", e)
        return {"status": "error", "payload": "Missing dependency 'websockets'. Install it in this venv."}

    try:
        async with websockets.connect(MCP_SERVER_URL) as websocket:  # type: ignore
            await websocket.send(json.dumps(message))
            response_str = await websocket.recv()
            try:
                return json.loads(response_str)
            except Exception:
                # Si Unity respondió texto plano, lo devolvemos literal
                return {"status": "ok", "payload": response_str}
    except Exception as e:
        log.error("Error WebSocket al conectar con %s: %s", MCP_SERVER_URL, e)
        return {"status": "error", "payload": f"WebSocket error: {e}"}


async def send_to_blender_and_get_response(message: Dict[str, Any]) -> Dict[str, Any]:
    """Conecta con el WebSocket de Blender y devuelve la respuesta como dict."""
    try:
        import websockets  # type: ignore
    except Exception as e:
        log.error("Falta el paquete 'websockets' para Blender: %s", e)
        return {"status": "error", "payload": "Missing dependency 'websockets'. Install it in this venv."}

    try:
        async with websockets.connect(BLENDER_SERVER_URL) as websocket:  # type: ignore
            await websocket.send(json.dumps(message))
            response_str = await websocket.recv()
            try:
                return json.loads(response_str)
            except Exception:
                return {"status": "ok", "payload": response_str}
    except Exception as e:
        log.error("Error WebSocket al conectar con %s: %s", BLENDER_SERVER_URL, e)
        return {"status": "error", "payload": f"WebSocket error: {e}"}


# ---------------------------------------------------------------------
# TOOLS (tus herramientas originales, adaptadas a logging y helpers)
# ---------------------------------------------------------------------

@mcp.tool()
async def unity_command(code: str) -> str:
    """
    Ejecuta un bloque de código C# directamente en el editor de Unity.
    Úsalo para crear GameObjects, añadir componentes, modificar propiedades, etc.
    """
    log.info("Executing command: %s...", code[:100])
    message = {"type": "command", "payload": {"code": code, "additional_references": []}}
    response = await send_to_unity_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


@mcp.tool()
async def unity_get_scene_hierarchy() -> str:
    """
    Devuelve una estructura de árbol en formato JSON con todos los GameObjects de la escena activa.
    """
    log.info("Executing query: get_scene_hierarchy...")
    message = {"type": "query", "action": "get_scene_hierarchy", "payload": "{}"}
    response = await send_to_unity_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


@mcp.tool()
async def unity_get_gameobject_details(instance_id: int) -> str:
    """
    Obtiene los componentes y propiedades de un GameObject específico usando su ID de instancia.
    """
    log.info("Executing query: get_gameobject_details for ID %s...", instance_id)
    payload_dict = {"instanceId": instance_id}
    message = {"type": "query", "action": "get_gameobject_details", "payload": payload_dict}
    response = await send_to_unity_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


@mcp.tool()
async def unity_get_project_files(path: str = ".") -> str:
    """
    Lista los archivos y subdirectorios de una ruta dentro de la carpeta 'Assets' del proyecto.
    """
    log.info("Executing query: get_project_files for path '%s'...", path)
    payload = json.dumps({"path": path})
    message = {"type": "query", "action": "get_project_files", "payload": payload}
    response = await send_to_unity_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


@mcp.tool()
async def unity_capture_screenshot() -> str:
    """
    Toma una captura de la ventana 'Game' de Unity y la guarda en el proyecto.
    """
    log.info("Executing query: capture_screenshot")
    
    message = {"type": "query", "action": "capture_screenshot", "payload": "{}"}
    response = await send_to_unity_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


# (Opcional) Tool de sanity check local
@mcp.tool()
def ping() -> str:
    """Comprobación rápida de vida del servidor MCP (no toca Unity)."""
    return "pong"


@mcp.tool()
async def unity_create_gameobject(name: str) -> str:
    """
    Crea un nuevo GameObject vacío en la escena de Unity.

    Args:
        name: El nombre para el nuevo GameObject.

    Returns:
        Una cadena JSON con la respuesta de Unity, que incluye el instanceId del objeto creado.
    """
    log.info(f"Executing tool: create_gameobject with name '{name}'")
    # El payload debe ser un string JSON, como define models.py
    payload_dict = {"name": name}
    message = {
        "type": "tool",
        "action": "CreateGameObject",
        "payload": json.dumps(payload_dict)
    }
    response = await send_to_unity_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


@mcp.tool()
async def unity_find_gameobject(name: str) -> str:
    """
    Busca un GameObject en la escena por su nombre.

    Args:
        name: El nombre del GameObject a buscar.

    Returns:
        Una cadena JSON con la respuesta de Unity, incluyendo el instanceId o -1 si no se encuentra.
    """
    log.info(f"Executing tool: find_gameobject with name '{name}'")
    payload_dict = {"name": name}
    message = {
        "type": "tool",
        "action": "FindGameObject",
        "payload": json.dumps(payload_dict)
    }
    response = await send_to_unity_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)

@mcp.tool()
async def unity_add_component(instanceId: int, componentType: str) -> str:
    """
    Añade un componente a un GameObject existente en Unity.

    Args:
        instanceId: El ID de instancia del GameObject.
        componentType: El nombre completo del tipo del componente (ej: "UnityEngine.Rigidbody").

    Returns:
        Una cadena JSON con la respuesta de Unity.
    """
    log.info(f"Executing tool: add_component of type '{componentType}' to object {instanceId}")
    payload_dict = {
        "instanceId": instanceId,
        "componentType": componentType
    }
    message = {
        "type": "tool",
        "action": "AddComponent",
        "payload": json.dumps(payload_dict)
    }
    response = await send_to_unity_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)

@mcp.tool()
async def unity_set_component_property(instanceId: int, componentType: str, propertyName: str, value: Any) -> str:
    """
    Establece el valor de una propiedad en un componente de un GameObject.

    Args:
        instanceId: El ID de instancia del GameObject.
        componentType: El nombre completo del tipo del componente.
        propertyName: El nombre de la propiedad a modificar.
        value: El nuevo valor (puede ser un primitivo como string/int/float, o un dict para vectores/colores).

    Returns:
        Una cadena JSON con la respuesta de Unity.
    """
    log.info(f"Executing tool: set_component_property '{propertyName}' on '{componentType}' for object {instanceId}")
    payload_dict = {
        "instanceId": instanceId,
        "componentType": componentType,
        "propertyName": propertyName,
        "value": value
    }
    message = {
        "type": "tool",
        "action": "SetComponentProperty",
        "payload": json.dumps(payload_dict)
    }
    response = await send_to_unity_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)



@mcp.tool()
async def blender_execute_python(code: str) -> str:
    """Ejecuta código Python en Blender y retorna stdout y stderr."""
    log.info("Blender execute_python")
    message = {"command": "execute_python", "params": {"code": code}}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_execute_python_file(path: str) -> str:
    """Ejecuta un archivo Python dentro del entorno de Blender.

    El archivo debe existir y ser accesible desde la instancia de Blender que
    recibe el comando. La respuesta incluye la salida estándar y cualquier
    error producido durante la ejecución.

    Args:
        path: Ruta al archivo Python desde la perspectiva de Blender.

    Returns:
        Una cadena JSON con la respuesta del puente de Blender, incluyendo
        stdout y stderr.
    """

    log.info("Blender execute_python_file: %s", path)
    message = {"command": "execute_python_file", "params": {"path": path}}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_run_macro(name: str, **kwargs: Any) -> str:
    """Ejecuta un macro predefinido en Blender.

    Args:
        name: Nombre del macro a ejecutar.
        **kwargs: Parámetros adicionales que se pasan al macro.

    Returns:
        La respuesta del puente de Blender con el resultado del macro.
    """
    log.info("Blender run_macro: %s", name)
    params = {"name": name, **kwargs}
    message = {"command": "run_macro", "params": params}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_create_cube(
    name: str = "Cube", location: Tuple[float, float, float] = (0, 0, 0)
) -> str:
    """Crea un cubo en la escena de Blender."""
    log.info("Blender create_cube: %s", name)
    payload = {"name": name, "location": list(location)}
    message = {"command": "create_cube", "params": payload}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_create_plane(
    name: str = "Plane", location: Tuple[float, float, float] = (0, 0, 0)
) -> str:
    """Crea un plano en la escena de Blender."""
    log.info("Blender create_plane: %s", name)
    payload = {"name": name, "location": list(location)}
    message = {"command": "create_plane", "params": payload}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_create_light(
    name: str = "Light",
    light_type: str = "POINT",
    location: Tuple[float, float, float] = (0, 0, 0),
) -> str:
    """Crea una luz en la escena de Blender."""
    log.info("Blender create_light: %s (%s)", name, light_type)
    payload = {
        "name": name,
        "light_type": light_type,
        "location": list(location),
    }
    message = {"command": "create_light", "params": payload}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_export_fbx(path: str) -> str:
    """Exporta la escena de Blender como un archivo FBX."""
    log.info("Blender export_fbx: %s", path)
    message = {"command": "export_fbx", "params": {"path": path}}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_transform(
    name: str,
    translation: Optional[Tuple[float, float, float]] = None,
    rotation: Optional[Tuple[float, float, float]] = None,
    scale: Optional[Tuple[float, float, float]] = None,
) -> str:
    """Aplica transformaciones a un objeto en Blender."""
    log.info("Blender transform: %s", name)
    params: Dict[str, Any] = {"name": name}
    if translation is not None:
        params["translation"] = list(translation)
    if rotation is not None:
        params["rotation"] = list(rotation)
    if scale is not None:
        params["scale"] = list(scale)
    message = {"command": "transform", "params": params}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)



# ---------------------------------------------------------------------
# Entrada principal: stdio (necesario para Gemini CLI)
# ---------------------------------------------------------------------
if __name__ == "__main__":
    # mcp.run() usa stdio por defecto.
    # Ejecuta este archivo con 'python -u' y/o PYTHONUNBUFFERED=1 para evitar delays de buffer.
    log.info("Arrancando servidor MCP 'unity_editor' (stdio). URL puente Unity: %s", MCP_SERVER_URL)
    mcp.run()
