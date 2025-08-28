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


# ---------------------------------------------------------------------
# Entrada principal: stdio (necesario para Gemini CLI)
# ---------------------------------------------------------------------
if __name__ == "__main__":
    # mcp.run() usa stdio por defecto.
    # Ejecuta este archivo con 'python -u' y/o PYTHONUNBUFFERED=1 para evitar delays de buffer.
    log.info("Arrancando servidor MCP 'unity_editor' (stdio). URL puente Unity: %s", MCP_SERVER_URL)
    mcp.run()

