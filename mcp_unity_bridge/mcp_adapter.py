# mcp_adapter.py
import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict, Optional, Tuple, List

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
# TOOLS Unity (sin cambios)
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


# ---------------------------------------------------------------------
# TOOLS Blender (actualizadas al websocket_server.py)
# ---------------------------------------------------------------------

@mcp.tool()
async def blender_execute_python(code: str) -> str:
    """
    Ejecuta código Python en Blender y retorna stdout y stderr.

    Ejemplo de llamada al servicio:
    {"command": "execute_python", "params": {"code": "print('hola')"}}
    """
    log.info("Blender execute_python")
    message = {"command": "execute_python", "params": {"code": code}}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_execute_python_file(path: str) -> str:
    """
    Ejecuta un archivo Python dentro del entorno de Blender.

    El archivo debe existir y ser accesible desde la instancia de Blender.

    Ejemplo de llamada al servicio:
    {"command": "execute_python_file", "params": {"path": "scripts/macro.py"}}
    """

    log.info("Blender execute_python_file: %s", path)
    message = {"command": "execute_python_file", "params": {"path": path}}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_identify() -> str:
    """
    Obtiene información de Blender y del servidor WebSocket.

    Ejemplo de llamada al servicio:
    {"command": "identify", "params": {}}
    """
    log.info("Blender identify")
    message = {"command": "identify", "params": {}}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_export_fbx(path: str) -> str:
    """
    Exporta la escena de Blender como un archivo FBX.

    Ejemplo de llamada al servicio:
    {"command": "export_fbx", "params": {"path": "Assets/Generated/model.fbx"}}
    """
    log.info("Blender export_fbx: %s", path)
    message = {"command": "export_fbx", "params": {"path": path}}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_geom_create_base(
    name: str,
    outline: Any,
    thickness: float = 0.2,
    mirror_x: bool = False,
) -> str:
    """
    Crea una base extruida a partir de un contorno 2D (XY).

    Ejemplo de llamada al servicio:
    {"command": "geom.create_base", "params": {"name":"Base","outline":[[0,0],[1,0],[1,1],[0,1]],"thickness":0.2,"mirror_x":false}}
    """
    log.info("Blender geom.create_base: %s", name)
    params: Dict[str, Any] = {
        "name": name,
        "outline": outline,
        "thickness": float(thickness),
        "mirror_x": bool(mirror_x),
    }
    message = {"command": "geom.create_base", "params": params}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_select_faces_by_range(object: str, conds: Any) -> str:
    """
    Selecciona caras cuyo centro cumpla un conjunto de rangos por eje.

    Ejemplo de llamada al servicio:
    {"command": "select.faces_by_range", "params": {"object": "Mesh", "conds": [{"axis":"y","min":0.0}]}}
    """
    log.info("Blender select.faces_by_range: %s", object)
    params = {"object": object, "conds": conds}
    message = {"command": "select.faces_by_range", "params": params}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_select_faces_in_bbox(object: str, bbox_min: Tuple[float, float, float], bbox_max: Tuple[float, float, float]) -> str:
    """
    Selecciona caras cuyo centro esté dentro de una caja AABB dada (min/max).

    Ejemplo de llamada al servicio:
    {"command": "select.faces_in_bbox", "params": {"object":"Mesh", "min":[-1,-1,-1], "max":[1,1,1]}}
    """
    log.info("Blender select.faces_in_bbox: %s", object)
    params = {"object": object, "min": list(bbox_min), "max": list(bbox_max)}
    message = {"command": "select.faces_in_bbox", "params": params}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_select_faces_by_normal(
    object: str,
    axis: Tuple[float, float, float] = (0, 0, 1),
    min_dot: float = 0.5,
    max_dot: float = 1.0,
) -> str:
    """
    Selecciona caras por dirección de normal según producto punto con un eje.

    Ejemplo de llamada al servicio:
    {"command": "select.faces_by_normal", "params": {"object":"Mesh","axis":[0,0,1],"min_dot":0.5,"max_dot":1.0}}
    """
    log.info("Blender select.faces_by_normal: %s", object)
    params = {"object": object, "axis": list(axis), "min_dot": float(min_dot), "max_dot": float(max_dot)}
    message = {"command": "select.faces_by_normal", "params": params}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_select_grow(object: str, selection_id: int, steps: int = 1) -> str:
    """
    Expande (crece) una selección de caras N veces siguiendo conectividad.

    Ejemplo de llamada al servicio:
    {"command": "select.grow", "params": {"object":"Mesh","selection_id":123,"steps":2}}
    """
    log.info("Blender select.grow: %s", object)
    params = {"object": object, "selection_id": int(selection_id), "steps": int(steps)}
    message = {"command": "select.grow", "params": params}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_select_verts_by_curvature(object: str, min_curv: float = 0.08, in_bbox: Optional[Dict[str, Any]] = None) -> str:
    """
    Selecciona vértices cuya curvatura aproximada supere un umbral (opcionalmente dentro de una AABB).

    Ejemplo de llamada al servicio:
    {"command": "select.verts_by_curvature", "params": {"object":"Mesh","min_curv":0.1,"in_bbox":{"min":[-1,-1,-1],"max":[1,1,1]}}}
    """
    log.info("Blender select.verts_by_curvature: %s", object)
    params: Dict[str, Any] = {"object": object, "min_curv": float(min_curv)}
    if in_bbox is not None:
        params["in_bbox"] = in_bbox
    message = {"command": "select.verts_by_curvature", "params": params}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_edit_extrude_selection(
    object: str,
    selection_id: int,
    translate: Tuple[float, float, float] = (0, 0, 0),
    scale_about_center: Tuple[float, float, float] = (1, 1, 1),
    inset: float = 0.0,
) -> str:
    """
    Extruye la selección de caras y aplica transformaciones locales.

    Ejemplo de llamada al servicio:
    {"command": "edit.extrude_selection", "params": {"object":"Mesh","selection_id":123,"translate":[0,0,0.2],"scale_about_center":[1,1,1],"inset":0.02}}
    """
    log.info("Blender edit.extrude_selection: %s", object)
    params = {
        "object": object,
        "selection_id": int(selection_id),
        "translate": list(translate),
        "scale_about_center": list(scale_about_center),
        "inset": float(inset),
    }
    message = {"command": "edit.extrude_selection", "params": params}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_edit_move_verts(
    object: str,
    selection_id: int,
    translate: Tuple[float, float, float] = (0, 0, 0),
    scale_about_center: Tuple[float, float, float] = (1, 1, 1),
) -> str:
    """
    Mueve y/o escala los vértices de una selección.

    Ejemplo de llamada al servicio:
    {"command": "edit.move_verts", "params": {"object":"Mesh","selection_id":123,"translate":[0,0,0.1],"scale_about_center":[1,1,1]}}
    """
    log.info("Blender edit.move_verts: %s", object)
    params = {
        "object": object,
        "selection_id": int(selection_id),
        "translate": list(translate),
        "scale_about_center": list(scale_about_center),
    }
    message = {"command": "edit.move_verts", "params": params}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_edit_sculpt_selection(object: str, selection_id: int, moves: Any) -> str:
    """
    Esculpe una selección aplicando una lista de movimientos sobre vértices/caras.

    Nota: El servidor espera la clave 'move' (no 'moves').

    Ejemplo de llamada al servicio:
    {"command": "edit.sculpt_selection", "params": {"object":"Mesh","selection_id":123,"move":[{"translate":[0,0,0.1]}]}}
    """
    log.info("Blender edit.sculpt_selection: %s", object)
    params = {"object": object, "selection_id": int(selection_id), "move": moves}
    message = {"command": "edit.sculpt_selection", "params": params}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_geom_mirror_x(object: str, merge_dist: float = 0.0008) -> str:
    """
    Espeja la malla respecto al eje X y fusiona vértices cercanos.

    Ejemplo de llamada al servicio:
    {"command": "geom.mirror_x", "params": {"object":"Mesh","merge_dist":0.0008}}
    """
    log.info("Blender geom.mirror_x: %s", object)
    params = {"object": object, "merge_dist": float(merge_dist)}
    message = {"command": "geom.mirror_x", "params": params}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_geom_cleanup(object: str, merge_dist: float = 0.0008, recalc: bool = True) -> str:
    """
    Limpieza de geometría: soldar vértices y recálculo opcional de normales.

    Ejemplo de llamada al servicio:
    {"command": "geom.cleanup", "params": {"object":"Mesh","merge_dist":0.001,"recalc":true}}
    """
    log.info("Blender geom.cleanup: %s", object)
    params = {"object": object, "merge_dist": float(merge_dist), "recalc": bool(recalc)}
    message = {"command": "geom.cleanup", "params": params}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_mesh_stats(object: str) -> str:
    """
    Devuelve estadísticas de la malla (caras, tris aproximados, AABB, etc.).

    Ejemplo de llamada al servicio:
    {"command": "mesh.stats", "params": {"object":"Mesh"}}
    """
    log.info("Blender mesh.stats: %s", object)
    message = {"command": "mesh.stats", "params": {"object": object}}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_mesh_validate(object: str, check_self_intersections: bool = False) -> str:
    """
    Valida la malla y opcionalmente detecta auto-intersecciones.

    Ejemplo de llamada al servicio:
    {"command": "mesh.validate", "params": {"object":"Mesh","check_self_intersections":false}}
    """
    log.info("Blender mesh.validate: %s", object)
    params = {"object": object, "check_self_intersections": bool(check_self_intersections)}
    message = {"command": "mesh.validate", "params": params}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_mesh_snapshot(object: str) -> str:
    """
    Crea un snapshot efímero de la malla para poder restaurar más tarde.

    Ejemplo de llamada al servicio:
    {"command": "mesh.snapshot", "params": {"object":"Mesh"}}
    """
    log.info("Blender mesh.snapshot: %s", object)
    message = {"command": "mesh.snapshot", "params": {"object": object}}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_mesh_restore(snapshot_id: int, object: Optional[str] = None) -> str:
    """
    Restaura una malla desde un snapshot previo.

    Ejemplo de llamada al servicio:
    {"command": "mesh.restore", "params": {"snapshot_id": 42, "object": "Mesh"}}
    """
    log.info("Blender mesh.restore: %s", snapshot_id)
    params: Dict[str, Any] = {"snapshot_id": int(snapshot_id)}
    if object is not None:
        params["object"] = object
    message = {"command": "mesh.restore", "params": params}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_similarity_iou_top(
    object: str,
    image_path: str,
    res: int = 256,
    margin: float = 0.05,
    threshold: float = 0.5,
) -> str:
    """
    Compara la silueta superior (XY) con una imagen binaria y devuelve IoU.

    Ejemplo de llamada al servicio:
    {"command": "similarity.iou_top", "params": {"object":"Mesh","image_path":"ref.png","res":256,"margin":0.05,"threshold":0.5}}
    """
    log.info("Blender similarity.iou_top: %s", object)
    params = {
        "object": object,
        "image_path": image_path,
        "res": int(res),
        "margin": float(margin),
        "threshold": float(threshold),
    }
    message = {"command": "similarity.iou_top", "params": params}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_similarity_iou_side(
    object: str,
    image_path: str,
    res: int = 256,
    margin: float = 0.05,
    threshold: float = 0.5,
) -> str:
    """
    Compara la silueta lateral (XZ) con una imagen binaria y devuelve IoU.

    Ejemplo de llamada al servicio:
    {"command": "similarity.iou_side", "params": {"object":"Mesh","image_path":"ref.png","res":256,"margin":0.05,"threshold":0.5}}
    """
    log.info("Blender similarity.iou_side: %s", object)
    params = {
        "object": object,
        "image_path": image_path,
        "res": int(res),
        "margin": float(margin),
        "threshold": float(threshold),
    }
    message = {"command": "similarity.iou_side", "params": params}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_similarity_iou_combo(
    object: str,
    image_top: str,
    image_side: str,
    res: int = 256,
    margin: float = 0.05,
    threshold: float = 0.5,
    alpha: float = 0.5,
) -> str:
    """
    IoU combinado de TOP(XY) y SIDE(XZ) ponderado por alpha.

    Ejemplo de llamada al servicio:
    {"command": "similarity.iou_combo", "params": {"object":"Mesh","image_top":"top.png","image_side":"side.png","res":256,"margin":0.05,"threshold":0.5,"alpha":0.5}}
    """
    log.info("Blender similarity.iou_combo: %s", object)
    params = {
        "object": object,
        "image_top": image_top,
        "image_side": image_side,
        "res": int(res),
        "margin": float(margin),
        "threshold": float(threshold),
        "alpha": float(alpha),
    }
    message = {"command": "similarity.iou_combo", "params": params}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_merge_stitch(
    object_a: str,
    object_b: str,
    out_name: str = "Merged",
    delete: str = "B_inside_A",
    weld_dist: float = 0.001,
    res: int = 256,
    margin: float = 0.03,
) -> str:
    """
    Fusiona dos mallas en un único objeto, recortando interiores y soldando vértices.

    Ejemplo de llamada al servicio:
    {"command": "merge.stitch", "params": {"object_a":"A","object_b":"B","out_name":"Merged","delete":"B_inside_A","weld_dist":0.001,"res":256,"margin":0.03}}
    """
    log.info("Blender merge.stitch: %s + %s", object_a, object_b)
    params = {
        "object_a": object_a,
        "object_b": object_b,
        "out_name": out_name,
        "delete": delete,
        "weld_dist": float(weld_dist),
        "res": int(res),
        "margin": float(margin),
    }
    message = {"command": "merge.stitch", "params": params}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_mesh_normals_recalc(object: str, ensure_outside: bool = True) -> str:
    """
    Recalcula normales de la malla (opcionalmente asegura orientación hacia fuera).

    Ejemplo de llamada al servicio:
    {"command": "mesh.normals_recalc", "params": {"object":"Mesh","ensure_outside":true}}
    """
    log.info("Blender mesh.normals_recalc: %s", object)
    params = {"object": object, "ensure_outside": bool(ensure_outside)}
    message = {"command": "mesh.normals_recalc", "params": params}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# SIMILARITY: FRONT + COMBO3
# ---------------------------------------------------------------------------

@mcp.tool()
async def blender_similarity_iou_front(object: str, image_path: str, res: int = 256, margin: float = 0.05, threshold: float = 0.5) -> str:
    """
    Calcula IoU entre la silueta frontal (plano YZ local) del objeto y una imagen de referencia.

    Ejemplo de llamada al servicio:
    {"command": "similarity.iou_front", "params": {"object":"Model","image_path":"D:/refs/front.png","res":256,"margin":0.05,"threshold":0.5}}
    """
    log.info("Blender similarity.iou_front: %s", object)
    params = {"object": object, "image_path": image_path, "res": int(res), "margin": float(margin), "threshold": float(threshold)}
    message = {"command": "similarity.iou_front", "params": params}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_similarity_iou_combo3(
    object: str,
    image_top: str,
    image_side: str,
    image_front: str,
    res: int = 256,
    margin: float = 0.05,
    threshold: float = 0.5,
    alpha: float = 0.34,
    beta: float = 0.33,
    gamma: float = 0.33,
) -> str:
    """
    Calcula IoU combinado para 3 vistas (TOP/XY, SIDE/XZ, FRONT/YZ) con pesos alpha/beta/gamma (suman ≈1).

    Ejemplo de llamada al servicio:
    {"command": "similarity.iou_combo3",
     "params": {"object":"Model","image_top":"D:/refs/top.png","image_side":"D:/refs/side.png","image_front":"D:/refs/front.png",
                "res":256,"margin":0.05,"threshold":0.5,"alpha":0.34,"beta":0.33,"gamma":0.33}}
    """
    log.info("Blender similarity.iou_combo3: %s", object)
    params = {
        "object": object,
        "image_top": image_top,
        "image_side": image_side,
        "image_front": image_front,
        "res": int(res),
        "margin": float(margin),
        "threshold": float(threshold),
        "alpha": float(alpha),
        "beta": float(beta),
        "gamma": float(gamma),
    }
    message = {"command": "similarity.iou_combo3", "params": params}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# SELECTION: EDGE LOOPS & RINGS
# ---------------------------------------------------------------------------

@mcp.tool()
async def blender_select_edge_loop_from_edge(object: str, edge_index: int) -> str:
    """
    Selecciona un edge-loop partiendo del índice de una arista. Devuelve selection_id y recuento.

    Ejemplo:
    {"command": "select.edge_loop_from_edge", "params": {"object":"Model","edge_index":120}}
    """
    log.info("Blender select.edge_loop_from_edge: %s (edge=%s)", object, edge_index)
    params = {"object": object, "edge_index": int(edge_index)}
    message = {"command": "select.edge_loop_from_edge", "params": params}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_select_edge_ring_from_edge(object: str, edge_index: int) -> str:
    """
    Selecciona un edge-ring partiendo del índice de una arista. Devuelve selection_id y recuento.

    Ejemplo:
    {"command": "select.edge_ring_from_edge", "params": {"object":"Model","edge_index":120}}
    """
    log.info("Blender select.edge_ring_from_edge: %s (edge=%s)", object, edge_index)
    params = {"object": object, "edge_index": int(edge_index)}
    message = {"command": "select.edge_ring_from_edge", "params": params}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# LOOP CUT / SUBDIVISIÓN
# ---------------------------------------------------------------------------

@mcp.tool()
async def blender_mesh_loop_insert(
    object: str,
    edges: Optional[List[int]] = None,
    selection_id: Optional[int] = None,
    cuts: int = 1,
    smooth: float = 0.0,
) -> str:
    """
    Inserta cortes a lo largo de un conjunto de aristas (loop/ring). Acepta lista de edges o selection_id con edges.

    Ejemplo:
    {"command":"mesh.loop_insert","params":{"object":"Model","selection_id":7,"cuts":2,"smooth":0.0}}
    """
    log.info("Blender mesh.loop_insert: %s (cuts=%s)", object, cuts)
    params = {"object": object, "edges": edges, "selection_id": selection_id, "cuts": int(cuts), "smooth": float(smooth)}
    message = {"command": "mesh.loop_insert", "params": params}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# BEVEL PARAMÉTRICO
# ---------------------------------------------------------------------------

@mcp.tool()
async def blender_mesh_bevel(
    object: str,
    edges: Optional[List[int]] = None,
    verts: Optional[List[int]] = None,
    selection_id: Optional[int] = None,
    offset: float = 0.01,
    segments: int = 2,
    profile: float = 0.7,
    clamp: bool = True,
    auto_sharp_angle: Optional[float] = None,
) -> str:
    """
    Aplica bevel (bmesh.ops.bevel) sobre edges/verts (sin bpy.ops).
    Puede derivar la selección desde selection_id o usar edges/verts directos.
    'auto_sharp_angle' detecta aristas “duras” automáticamente (en grados).

    Ejemplo:
    {"command":"mesh.bevel","params":{"object":"Model","selection_id":7,"offset":0.01,"segments":3,"profile":0.7,"clamp":true}}
    """
    log.info("Blender mesh.bevel: %s (offset=%s, segments=%s)", object, offset, segments)
    params = {
        "object": object,
        "edges": edges,
        "verts": verts,
        "selection_id": selection_id,
        "offset": float(offset),
        "segments": int(segments),
        "profile": float(profile),
        "clamp": bool(clamp),
        "auto_sharp_angle": float(auto_sharp_angle) if auto_sharp_angle is not None else None,
    }
    message = {"command": "mesh.bevel", "params": params}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# GEODESIC SELECT
# ---------------------------------------------------------------------------

@mcp.tool()
async def blender_select_geodesic(object: str, seed_vert: Optional[int] = None, selection_id: Optional[int] = None, radius: float = 0.25) -> str:
    """
    Selecciona vértices por distancia geodésica a lo largo de la superficie desde una semilla (vert o selection_id).

    Ejemplo:
    {"command":"select.geodesic","params":{"object":"Model","seed_vert":42,"radius":0.3}}
    """
    log.info("Blender select.geodesic: %s (seed=%s, radius=%s)", object, seed_vert, radius)
    params = {"object": object, "seed_vert": seed_vert, "selection_id": selection_id, "radius": float(radius)}
    message = {"command": "select.geodesic", "params": params}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# SNAP A SILUETA (IMAGEN)
# ---------------------------------------------------------------------------

@mcp.tool()
async def blender_edit_snap_to_silhouette(
    object: str,
    selection_id: int,
    plane: str = "XY",
    image_path: str = "",
    strength: float = 0.5,
    iterations: int = 8,
    step: float = 1.0,
    res: int = 256,
    margin: float = 0.05,
    threshold: float = 0.5,
) -> str:
    """
    Atrae vértices seleccionados hacia el borde de una silueta 2D (imagen) en el plano dado (XY/XZ/YZ).

    Ejemplo:
    {"command":"edit.snap_to_silhouette","params":{
      "object":"Model","selection_id":7,"plane":"XY","image_path":"D:/refs/top.png",
      "strength":0.6,"iterations":8,"step":1.0,"res":256,"margin":0.05,"threshold":0.5}}
    """
    log.info("Blender edit.snap_to_silhouette: %s (plane=%s)", object, plane)
    params = {
        "object": object,
        "selection_id": int(selection_id),
        "plane": plane,
        "image_path": image_path,
        "strength": float(strength),
        "iterations": int(iterations),
        "step": float(step),
        "res": int(res),
        "margin": float(margin),
        "threshold": float(threshold),
    }
    message = {"command": "edit.snap_to_silhouette", "params": params}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# LANDMARKS 2D → 3D
# ---------------------------------------------------------------------------

@mcp.tool()
async def blender_constraint_landmarks_apply(object: str, plane: str = "XY", points: List[dict] = []) -> str:
    """
    Aplica landmarks 2D (uv en 0..1) con radio/strength en el plano indicado.
    Cada punto: {"uv":[u,v], "radius":0.1, "strength":0.8}

    Ejemplo:
    {"command":"constraint.landmarks_apply","params":{
      "object":"Model","plane":"YZ","points":[{"uv":[0.62,0.38],"radius":0.08,"strength":0.9}]}}
    """
    log.info("Blender constraint.landmarks_apply: %s (plane=%s, points=%d)", object, plane, len(points) if points else 0)
    params = {"object": object, "plane": plane, "points": points or []}
    message = {"command": "constraint.landmarks_apply", "params": params}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# SIMETRÍAS AVANZADAS
# ---------------------------------------------------------------------------

@mcp.tool()
async def blender_geom_mirror_plane(
    object: str,
    plane_point: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    plane_normal: Tuple[float, float, float] = (1.0, 0.0, 0.0),
    merge_dist: float = 0.0008,
) -> str:
    """
    Duplica y refleja la malla respecto a un plano arbitrario (punto + normal). Suelda con merge_dist.

    Ejemplo:
    {"command":"geom.mirror_plane","params":{"object":"Model","plane_point":[0,0,0],"plane_normal":[0.3,0.7,0.6],"merge_dist":0.0008}}
    """
    log.info("Blender geom.mirror_plane: %s", object)
    params = {"object": object, "plane_point": list(plane_point), "plane_normal": list(plane_normal), "merge_dist": float(merge_dist)}
    message = {"command": "geom.mirror_plane", "params": params}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_geom_symmetry_radial(object: str, axis: str = "Z", count: int = 6, merge_dist: float = 0.0008) -> str:
    """
    Simetría radial n-fold duplicando y rotando la malla alrededor del eje local indicado. Suelda con merge_dist.

    Ejemplo:
    {"command":"geom.symmetry_radial","params":{"object":"Model","axis":"Z","count":8,"merge_dist":0.0008}}
    """
    log.info("Blender geom.symmetry_radial: %s (axis=%s, count=%s)", object, axis, count)
    params = {"object": object, "axis": axis, "count": int(count), "merge_dist": float(merge_dist)}
    message = {"command": "geom.symmetry_radial", "params": params}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# TOPOLOGÍA & REPARACIÓN
# ---------------------------------------------------------------------------

@mcp.tool()
async def blender_mesh_triangulate_beautify(object: str) -> str:
    """
    Triangula la malla y aplica 'beautify' para mejorar la calidad angular.

    Ejemplo:
    {"command":"mesh.triangulate_beautify","params":{"object":"Model"}}
    """
    log.info("Blender mesh.triangulate_beautify: %s", object)
    params = {"object": object}
    message = {"command": "mesh.triangulate_beautify", "params": params}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_mesh_bridge_loops(object: str, loops: List[List[int]]) -> str:
    """
    Puentea bordes entre loops (cada loop es una lista de índices de arista).

    Ejemplo:
    {"command":"mesh.bridge_loops","params":{"object":"Model","loops":[[10,11,12],[47,48,49]]}}
    """
    log.info("Blender mesh.bridge_loops: %s (loops=%d)", object, len(loops) if loops else 0)
    params = {"object": object, "loops": loops}
    message = {"command": "mesh.bridge_loops", "params": params}
    response = await send_to_blender_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_mesh_fill_holes(object: str) -> str:
    """
    Rellena agujeros detectando bordes frontera (len(link_faces)==1).

    Ejemplo:
    {"command":"mesh.fill_holes","params":{"object":"Model"}}
    """
    log.info("Blender mesh.fill_holes: %s", object)
    params = {"object": object}
    message = {"command": "mesh.fill_holes", "params": params}
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

