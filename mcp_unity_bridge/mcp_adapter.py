# mcp_adapter.py
import asyncio
import atexit
import json
import logging
import os
from pathlib import Path
import sys
from typing import Any, Dict, Optional, Tuple, List

# SDK MCP (stdio por defecto) o Dummy en modo test
_TESTMODE = os.getenv("AGP_ADAPTER_TESTMODE", "0") == "1"
if _TESTMODE:
    class _DummyMCP:
        def tool(self):
            def deco(fn):
                return fn
            return deco
        def run(self):
            # Quedarse vivo leyendo stdin para simular servidor
            try:
                while True:
                    data = sys.stdin.buffer.readline()
                    if not data:
                        break
            except Exception:
                pass
    FastMCP = None  # type: ignore
    _USING_DUMMY = True
else:
    from mcp.server.fastmcp import FastMCP
    _USING_DUMMY = False

# ---------------------------------------------------------------------
# Logging SIEMPRE a stderr (stdout queda limpio para el protocolo MCP)
# ---------------------------------------------------------------------
try:
    from src.logging_system import LogManager  # type: ignore
except Exception:
    LogManager = None  # type: ignore

if LogManager is not None:
    _lm = LogManager(component="unity_mcp_adapter")
    log = _lm.get_logger()
else:
    handler = logging.StreamHandler(sys.stderr)
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
    log = logging.getLogger("unity_mcp_adapter")

# ---------------------------------------------------------------------
# Instancia MCP o Dummy: el nombre debe coincidir con settings.json (unity_editor)
# ---------------------------------------------------------------------
mcp = _DummyMCP() if _TESTMODE else FastMCP("unity_editor")

# ---------------------------------------------------------------------
# URL del puente Unity (puedes sobreescribir con la variable de entorno)
# ---------------------------------------------------------------------
"""Capa de configuración centralizada"""
# Ensure src is on path for local runs
_here = os.path.dirname(__file__)
_src_path = os.path.join(_here, "src")
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)
try:
    from src.config_manager import ConfigManager  # type: ignore
except Exception:
    ConfigManager = None  # type: ignore

if ConfigManager is not None:
    _cfg = ConfigManager().get()
    _mcp_default_url = f"ws://{_cfg.servers.mcp_bridge.host}:{_cfg.servers.mcp_bridge.port}/ws/gemini_cli_adapter"
else:
    _mcp_default_url = "ws://127.0.0.1:8001/ws/gemini_cli_adapter"

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", _mcp_default_url)

# ---------------------------------------------------------------------
# Configuración del puente Blender y rutas compartidas
# ---------------------------------------------------------------------
if ConfigManager is not None:
    _cfg = ConfigManager().get()
    _blender_default_url = f"ws://{_cfg.servers.blender_addon.host}:{_cfg.servers.blender_addon.port}"
    BLENDER_SERVER_URL = os.getenv("BLENDER_SERVER_URL", _blender_default_url)
    BASE_DIR = str(ConfigManager().get_repo_root())
    UNITY_PROJECT_DIR = str(_cfg.paths.unity_project)
else:
    BLENDER_SERVER_URL = os.getenv("BLENDER_SERVER_URL", "ws://127.0.0.1:8002")
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    UNITY_PROJECT_DIR = os.path.join(BASE_DIR, "unity_project")


# ---------------------------------------------------------------------
# Single-instance lock (Windows-friendly; works cross-platform)
# ---------------------------------------------------------------------
import tempfile
import time

_LOCK_PATH = os.path.join(os.environ.get("TEMP", tempfile.gettempdir()), "agp_mcp_adapter.lock")


def _is_pid_alive(pid: int) -> bool:
    try:
        if pid <= 0:
            return False
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            STILL_ACTIVE = 259
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            OpenProcess = kernel32.OpenProcess
            OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            OpenProcess.restype = wintypes.HANDLE
            GetExitCodeProcess = kernel32.GetExitCodeProcess
            GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
            GetExitCodeProcess.restype = wintypes.BOOL
            CloseHandle = kernel32.CloseHandle
            CloseHandle.argtypes = [wintypes.HANDLE]
            CloseHandle.restype = wintypes.BOOL

            h = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not h:
                return False
            try:
                code = wintypes.DWORD()
                if not GetExitCodeProcess(h, ctypes.byref(code)):
                    return False
                return int(code.value) == STILL_ACTIVE
            finally:
                try:
                    CloseHandle(h)
                except Exception:
                    pass
        else:
            # POSIX
            os.kill(pid, 0)
            return True
    except Exception:
        return False


def _read_lock() -> Optional[Dict[str, Any]]:
    try:
        if not os.path.exists(_LOCK_PATH):
            return None
        data = Path(_LOCK_PATH).read_text(encoding="utf-8")
        obj = json.loads(data)
        if not isinstance(obj, dict):
            return None
        return obj
    except Exception:
        return None


def _write_lock(pid: int) -> None:
    payload = {"pid": int(pid), "startedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    try:
        Path(_LOCK_PATH).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _clear_lock() -> None:
    try:
        if os.path.exists(_LOCK_PATH):
            os.remove(_LOCK_PATH)
    except Exception:
        pass


def _acquire_single_instance_or_exit() -> None:
    try:
        existing = _read_lock()
        if existing:
            pid = int(existing.get("pid") or 0)
            if _is_pid_alive(pid):
                msg = f"Adapter already running by PID={pid}. Refusing to start."
                try:
                    log.error(msg)
                except Exception:
                    pass
                # Exit without printing to stdout
                sys.stderr.write(msg + "\n")
                sys.stderr.flush()
                os._exit(1)
            else:
                # Stale lock; clean up
                _clear_lock()
        _write_lock(os.getpid())
        atexit.register(_clear_lock)
    except Exception:
        # Best-effort; continue without lock
        try:
            log.warning("Failed to manage adapter lock; proceeding anyway")
        except Exception:
            pass


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
# TOOLS Blender 
# ---------------------------------------------------------------------

def _ensure_json_obj(value: Any) -> Dict[str, Any]:
    """Acepta un dict o una cadena JSON y devuelve un dict.

    Si `value` es None, devuelve {}. Lanza ValueError si no es parseable.
    """
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            obj = json.loads(value)
        except Exception as e:
            raise ValueError(f"params JSON inválido: {e}")
        if not isinstance(obj, dict):
            raise ValueError("se esperaba un objeto JSON (dict)")
        return obj
    raise ValueError("se esperaba un dict o una cadena JSON no vacía")


def _ensure_json_list(value: Any) -> List[Any]:
    """Acepta una lista o una cadena JSON y devuelve una lista."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        try:
            arr = json.loads(value)
        except Exception as e:
            raise ValueError(f"lista JSON inválida: {e}")
        if not isinstance(arr, list):
            raise ValueError("se esperaba una lista JSON")
        return arr
    raise ValueError("se esperaba una lista o una cadena JSON no vacía")


async def _blender_request(command: str, params: Dict[str, Any], timeout: Optional[float] = None) -> Dict[str, Any]:
    msg: Dict[str, Any] = {"command": command, "params": params}
    if timeout is not None:
        try:
            t = float(timeout)
            if t > 0:
                msg["timeout"] = t
        except Exception:
            pass
    return await send_to_blender_and_get_response(msg)


@mcp.tool()
async def blender_identify() -> str:
    """Consulta de identificación del servidor Blender (versión, módulo, ws).

    Ejemplo:
      blender_identify() -> { "status":"ok", "result": { "blender_version":[4,5,0], ... } }
    """
    resp = await send_to_blender_and_get_response({"identify": True})
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_list_commands() -> str:
    """Lista todos los comandos disponibles en el add-on de Blender.

    Ejemplo:
      blender_list_commands() -> { "status":"ok", "result": {"commands":["scene.clear", ...]} }
    """
    resp = await _blender_request("server.list_commands", {})
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_call(command: str, params: Any = "{}", timeout: Optional[float] = None) -> str:
    """Invoca directamente un comando del add-on de Blender.

    Args:
      - command: nombre completo, p. ej. "scene.clear" o "helpers.capture_view".
      - params: dict o cadena JSON con los parámetros del comando.
      - timeout: opcional, segundos para este request (1..300).

    Ejemplos:
      - Limpiar escena:
          blender_call("scene.clear", "{}")
      - Crear primitiva:
          blender_call("modeling.create_primitive", {"kind":"cube","params":{"size":2.0},"name":"Box"})
      - Snapshot viewport:
          blender_call("helpers.capture_view", {"view":"front","width":512,"height":512})
      - Ejecutar código Python:
          blender_call("helpers.exec_python", {"code":"RESULT=2+3","return_variable":"RESULT"})
    """
    p = _ensure_json_obj(params) if not isinstance(params, dict) else params
    resp = await _blender_request(command, p, timeout=timeout)
    return json.dumps(resp, indent=2, ensure_ascii=False)


# ---- Wrappers frecuentes (ergonomía y ejemplos claros) ----

@mcp.tool()
async def blender_capture_view(
    view: str = "front",
    width: int = 768,
    height: int = 768,
    perspective: bool = False,
    shading: str = "SOLID",
    return_base64: bool = True,
    overlay_wireframe: bool = False,
    enhance: bool = False,
    solid_wire: bool = False,
    color_type: Optional[str] = None,
) -> str:
    """Realiza un snapshot del viewport 3D.

    Ejemplo:
      blender_capture_view(view="iso", perspective=True, width=640, height=640, solid_wire=True)
    """
    params: Dict[str, Any] = {
        "view": view,
        "width": int(width),
        "height": int(height),
        "perspective": bool(perspective),
        "shading": shading,
        "return_base64": bool(return_base64),
        "overlay_wireframe": bool(overlay_wireframe),
        "enhance": bool(enhance),
        "solid_wire": bool(solid_wire),
    }
    if color_type:
        params["color_type"] = color_type
    resp = await _blender_request("helpers.capture_view", params)
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_exec_python(
    code: Optional[str] = None,
    path: Optional[str] = None,
    return_variable: Optional[str] = None,
    globals_json: Any = None,
) -> str:
    """Ejecuta código o un script Python dentro de Blender.

    Debes pasar exactamente uno de `code` o `path`.

    Ejemplos:
      - Inline: blender_exec_python(code="x=21*2\nRESULT=x", return_variable="RESULT")
      - Archivo: blender_exec_python(path="D:/tmp/script.py")
    """
    params: Dict[str, Any] = {}
    if code:
        params["code"] = code
    if path:
        params["path"] = path
    if return_variable:
        params["return_variable"] = return_variable
    if globals_json is not None:
        try:
            params["globals"] = _ensure_json_obj(globals_json) if not isinstance(globals_json, dict) else globals_json
        except Exception:
            params["globals"] = globals_json
    resp = await _blender_request("helpers.exec_python", params)
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_scene_clear() -> str:
    """Limpia la escena: elimina objetos y purga huérfanos.

    Ejemplo: blender_scene_clear()
    """
    resp = await _blender_request("scene.clear", {})
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_modeling_create_primitive(
    kind: str,
    params_json: Any = None,
    name: Optional[str] = None,
    collection: Optional[str] = None,
    location: Optional[List[float]] = None,
    rotation: Optional[List[float]] = None,
    scale: Optional[List[float]] = None,
) -> str:
    """Crea una primitiva de malla sin bpy.ops.

    Ejemplo:
      blender_modeling_create_primitive(
          kind="cube",
          params_json={"size":2.0},
          name="MyCube",
          location=[0,0,0], rotation=[0,0,0], scale=[1,1,1]
      )
    """
    payload: Dict[str, Any] = {"kind": kind}
    if params_json is not None:
        payload["params"] = _ensure_json_obj(params_json) if not isinstance(params_json, dict) else params_json
    if name:
        payload["name"] = name
    if collection:
        payload["collection"] = collection
    if location:
        payload["location"] = list(location)
    if rotation:
        payload["rotation"] = list(rotation)
    if scale:
        payload["scale"] = list(scale)
    resp = await _blender_request("modeling.create_primitive", payload)
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_mesh_from_points(
    name: str,
    vertices: Any,
    faces: Any = None,
    edges: Any = None,
    collection: Optional[str] = None,
    recalc_normals: bool = True,
) -> str:
    """Crea un objeto malla desde vértices y caras/aristas opcionales.

    Ejemplo simple:
      blender_mesh_from_points(
        name="Triangle",
        vertices=[[0,0,0],[1,0,0],[0,1,0]],
        faces=[[0,1,2]]
      )
    """
    payload: Dict[str, Any] = {
        "name": name,
        "vertices": _ensure_json_list(vertices) if not isinstance(vertices, list) else vertices,
        "recalc_normals": bool(recalc_normals),
    }
    if faces is not None:
        payload["faces"] = _ensure_json_list(faces) if not isinstance(faces, list) else faces
    if edges is not None:
        payload["edges"] = _ensure_json_list(edges) if not isinstance(edges, list) else edges
    if collection:
        payload["collection"] = collection
    resp = await _blender_request("mesh.from_points", payload)
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_mesh_validate_and_heal(
    object_name: str,
    weld_distance: float = 1e-5,
    fix_normals: bool = True,
    dissolve_threshold: float = 0.01,
) -> str:
    """Valida y repara una malla (weld, dissolve, recalc normals opcional).

    Ejemplo:
      blender_mesh_validate_and_heal("Cube", weld_distance=1e-4, dissolve_threshold=0.02)
    """
    payload = {
        "object": object_name,
        "weld_distance": float(weld_distance),
        "fix_normals": bool(fix_normals),
        "dissolve_threshold": float(dissolve_threshold),
    }
    resp = await _blender_request("mesh.validate_and_heal", payload)
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_mod_add_mirror(object_name: str, axis: str = "X", use_clip: bool = True, merge_threshold: float = 1e-4) -> str:
    """Añade un Mirror a un objeto MESH.

    Ejemplo: blender_mod_add_mirror("Cube", axis="X", use_clip=True)
    """
    payload = {"object": object_name, "axis": axis, "use_clip": bool(use_clip), "merge_threshold": float(merge_threshold)}
    resp = await _blender_request("mod.add_mirror", payload)
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_mod_add_subsurf(object_name: str, levels: int = 2) -> str:
    """Añade Subsurf a un objeto MESH.

    Ejemplo: blender_mod_add_subsurf("Cube", levels=2)
    """
    payload = {"object": object_name, "levels": int(levels)}
    resp = await _blender_request("mod.add_subsurf", payload)
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_mod_add_solidify(object_name: str, thickness: float = 0.05, offset: float = 0.0) -> str:
    """Añade Solidify (grosor de paredes) a un objeto MESH.

    Ejemplo: blender_mod_add_solidify("Cube", thickness=0.1, offset=0.0)
    """
    payload = {"object": object_name, "thickness": float(thickness), "offset": float(offset)}
    resp = await _blender_request("mod.add_solidify", payload)
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_mod_apply_all(object_name: str) -> str:
    """Aplica todos los modificadores de un objeto.

    Ejemplo: blender_mod_apply_all("Cube")
    """
    resp = await _blender_request("mod.apply_all", {"object": object_name})
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_edit_extrude_normal(object_name: str, face_indices: Any, amount: float) -> str:
    """Extruye caras por sus normales.

    Ejemplo: blender_edit_extrude_normal("Cube", face_indices=[0,1,2,3], amount=0.05)
    """
    payload = {
        "object": object_name,
        "face_indices": _ensure_json_list(face_indices) if not isinstance(face_indices, list) else face_indices,
        "amount": float(amount),
    }
    resp = await _blender_request("edit.extrude_normal", payload)
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_edit_bevel_edges(object_name: str, edge_indices: Any, offset: float, segments: int = 2, clamp_overlap: bool = True) -> str:
    """Bevel de aristas seleccionadas.

    Ejemplo: blender_edit_bevel_edges("Cube", edge_indices=list(range(12)), offset=0.02, segments=2)
    """
    payload = {
        "object": object_name,
        "edge_indices": _ensure_json_list(edge_indices) if not isinstance(edge_indices, list) else edge_indices,
        "offset": float(offset),
        "segments": int(segments),
        "clamp_overlap": bool(clamp_overlap),
    }
    resp = await _blender_request("edit.bevel_edges", payload)
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_topology_cleanup_basic(object_name: str, merge_distance: float = 1e-4, limited_angle: float = 0.349, force_tris: bool = False) -> str:
    """Limpieza básica de topología (merge, dissolve limitado, triangulado opcional).

    Ejemplo: blender_topology_cleanup_basic("Cube", merge_distance=1e-5)
    """
    payload = {
        "object": object_name,
        "merge_distance": float(merge_distance),
        "limited_angle": float(limited_angle),
        "force_tris": bool(force_tris),
    }
    resp = await _blender_request("topology.cleanup_basic", payload)
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_analysis_mesh_stats(object_name: str) -> str:
    """Métricas de malla (cuentas, bbox, área/volumen, calidad, simetría).

    Ejemplo: blender_analysis_mesh_stats("Cube")
    """
    resp = await _blender_request("analysis.mesh_stats", {"object": object_name})
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_analysis_non_manifold_edges(object_name: str) -> str:
    """Cuenta de aristas no manifold.

    Ejemplo: blender_analysis_non_manifold_edges("Cube")
    """
    resp = await _blender_request("analysis.non_manifold_edges", {"object": object_name})
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_topology_merge_by_distance(object_name: str, distance: float = 1e-4) -> str:
    """Funde (weld) vértices por distancia en toda la malla.

    Ejemplo: blender_topology_merge_by_distance("Cube", distance=1e-4)
    """
    payload = {"object": object_name, "distance": float(distance)}
    resp = await _blender_request("topology.merge_by_distance", payload)
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_normals_recalc(object_name: str, outside: bool = True) -> str:
    """Recalcula normales hacia fuera (outside=True) o hacia dentro (outside=False).

    Ejemplo: blender_normals_recalc("Cube", outside=True)
    """
    payload = {"object": object_name, "outside": bool(outside)}
    resp = await _blender_request("normals.recalc", payload)
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_selection_store(object_name: str, mode: str = "FACE") -> str:
    """Guarda la selección actual del objeto (VERT/EDGE/FACE) y devuelve un id.

    Ejemplo: blender_selection_store("Cube", mode="FACE")
    """
    resp = await _blender_request("selection.store", {"object": object_name, "mode": mode})
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_selection_restore(object_name: str, selection_id: str) -> str:
    """Restaura una selección guardada previamente por id.

    Ejemplo: blender_selection_restore("Cube", selection_id="s1")
    """
    resp = await _blender_request("selection.restore", {"object": object_name, "selection_id": selection_id})
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_ref_blueprints_setup(front: str, left: str, top: str, size: float = 1.0, opacity: float = 0.4, lock: bool = True) -> str:
    """Configura imágenes de referencia (front/left/top) como empties.

    Ejemplo: blender_ref_blueprints_setup("front.png","left.png","top.png", size=2.0)
    """
    payload = {"front": front, "left": left, "top": top, "size": float(size), "opacity": float(opacity), "lock": bool(lock)}
    resp = await _blender_request("ref.blueprints_setup", payload)
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_ref_blueprints_update(which: str, image: Optional[str] = None, opacity: Optional[float] = None, visible: Optional[bool] = None) -> str:
    """Actualiza una blueprint (imagen/opacidad/visibilidad).

    Ejemplo: blender_ref_blueprints_update("front", opacity=0.6)
    """
    payload: Dict[str, Any] = {"which": which}
    if image is not None:
        payload["image"] = image
    if opacity is not None:
        payload["opacity"] = float(opacity)
    if visible is not None:
        payload["visible"] = bool(visible)
    resp = await _blender_request("ref.blueprints_update", payload)
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_ref_blueprints_remove() -> str:
    """Elimina los empties de referencia configurados.

    Ejemplo: blender_ref_blueprints_remove()
    """
    resp = await _blender_request("ref.blueprints_remove", {})
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_reference_fit_bbox_to_blueprint(
    object_name: str,
    view: str,
    image: Optional[str] = None,
    threshold: float = 0.5,
    uniform_scale: bool = False,
) -> str:
    """Ajusta el bbox proyectado del objeto a la silueta de la blueprint.

    Ejemplo: blender_reference_fit_bbox_to_blueprint("Cube", view="front", threshold=0.5)
    """
    payload: Dict[str, Any] = {
        "object": object_name,
        "view": view,
        "threshold": float(threshold),
        "uniform_scale": bool(uniform_scale),
    }
    if image:
        payload["image"] = image
    resp = await _blender_request("reference.fit_bbox_to_blueprint", payload)
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_mesh_poly_extrude_from_outline(
    name: str,
    points2d: Any,
    view: str,
    thickness: float = 0.2,
    triangulate: bool = True,
    collection: Optional[str] = None,
) -> str:
    """Crea un sólido extruido a partir de un contorno 2D en un plano cardinal.

    Ejemplo:
      blender_mesh_poly_extrude_from_outline(
        name="Badge",
        points2d=[[0,0],[1,0],[1,1],[0,1]],
        view="front",
        thickness=0.1,
        triangulate=True
      )
    """
    payload: Dict[str, Any] = {
        "name": name,
        "points2d": _ensure_json_list(points2d) if not isinstance(points2d, list) else points2d,
        "view": view,
        "thickness": float(thickness),
        "triangulate": bool(triangulate),
    }
    if collection:
        payload["collection"] = collection
    resp = await _blender_request("mesh.poly_extrude_from_outline", payload)
    return json.dumps(resp, indent=2, ensure_ascii=False)


# ---- Wrappers adicionales (cobertura completa del add-on) ----


@mcp.tool()
async def blender_server_ping() -> str:
    """Ping al add-on de Blender.

    Ejemplo: blender_server_ping()
    """
    resp = await _blender_request("server.ping", {})
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_topology_count_mesh_objects() -> str:
    """Cuenta los objetos MESH en la escena.

    Ejemplo: blender_topology_count_mesh_objects()
    """
    resp = await _blender_request("topology.count_mesh_objects", {})
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_topology_ensure_object_mode() -> str:
    """Asegura modo OBJECT y devuelve el modo actual.

    Ejemplo: blender_topology_ensure_object_mode()
    """
    resp = await _blender_request("topology.ensure_object_mode", {})
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_topology_touch_active() -> str:
    """Escritura no destructiva sobre la malla activa para forzar actualización.

    Ejemplo: blender_topology_touch_active()
    """
    resp = await _blender_request("topology.touch_active", {})
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_topology_bevel_edges(object_name: str, edge_indices: Any, offset: float, segments: int = 2, clamp: bool = True) -> str:
    """Bevel de aristas usando el comando de topología.

    Ejemplo: blender_topology_bevel_edges("Cube", edge_indices=[0,1], offset=0.02, segments=2)
    """
    payload = {
        "object": object_name,
        "edge_indices": _ensure_json_list(edge_indices) if not isinstance(edge_indices, list) else edge_indices,
        "offset": float(offset),
        "segments": int(segments),
        "clamp": bool(clamp),
    }
    resp = await _blender_request("topology.bevel_edges", payload)
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_scene_remove_object(name: str) -> str:
    """Elimina un objeto por nombre.

    Ejemplo: blender_scene_remove_object("Cube")
    """
    resp = await _blender_request("scene.remove_object", {"name": name})
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_modeling_echo(params_json: Any = None) -> str:
    """Echo de parámetros para depuración.

    Ejemplo: blender_modeling_echo({"hello":"world"})
    """
    p = _ensure_json_obj(params_json) if (params_json is not None and not isinstance(params_json, dict)) else (params_json or {})
    resp = await _blender_request("modeling.echo", p)
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_modeling_get_version() -> str:
    """Devuelve la versión de Blender.

    Ejemplo: blender_modeling_get_version()
    """
    resp = await _blender_request("modeling.get_version", {})
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_edit_inset_region(object_name: str, face_indices: Any, thickness: float, depth: float = 0.0) -> str:
    """Inset de una región de caras.

    Ejemplo: blender_edit_inset_region("Cube", face_indices=[0,1,2,3], thickness=0.02, depth=0.0)
    """
    payload = {
        "object": object_name,
        "face_indices": _ensure_json_list(face_indices) if not isinstance(face_indices, list) else face_indices,
        "thickness": float(thickness),
        "depth": float(depth),
    }
    resp = await _blender_request("edit.inset_region", payload)
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_normals_recalculate_selected() -> str:
    """Recalcula normales de todos los objetos MESH seleccionados.

    Ejemplo: blender_normals_recalculate_selected()
    """
    resp = await _blender_request("normals.recalculate_selected", {})
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_project_to_blueprint_plane(point: Any, view: str, empty: str) -> str:
    """Proyecta un punto [x,y,z] al plano de una blueprint y devuelve (u,v).

    Ejemplo: blender_project_to_blueprint_plane([0,0,0], view="front", empty="REF_FRONT")
    """
    payload = {"point": list(point), "view": view, "empty": empty}
    resp = await _blender_request("project.to_blueprint_plane", payload)
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_project_from_blueprint_plane(u: float, v: float, view: str, empty: str) -> str:
    """Convierte (u,v) de la blueprint a un punto 3D en el plano.

    Ejemplo: blender_project_from_blueprint_plane(100, 120, view="front", empty="REF_FRONT")
    """
    payload = {"u": float(u), "v": float(v), "view": view, "empty": empty}
    resp = await _blender_request("project.from_blueprint_plane", payload)
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_reference_outline_from_alpha(image: str, threshold: float = 0.5, simplify_tol: float = 2.0, max_points: int = 2048) -> str:
    """Extrae contorno desde alpha (fallback a luma si alpha no útil).

    Ejemplo: blender_reference_outline_from_alpha("D:/img.png", threshold=0.5)
    """
    payload = {"image": image, "threshold": float(threshold), "simplify_tol": float(simplify_tol), "max_points": int(max_points)}
    resp = await _blender_request("reference.outline_from_alpha", payload)
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_reference_outline_from_image(image: str, mode: str = "auto", threshold: Optional[float] = None, bg_color: Any = None, invert_luma: bool = False, simplify_tol: float = 0.0) -> str:
    """Extrae contorno de imagen tolerante a falta de alpha (auto/alpha/bg/luma).

    Ejemplo: blender_reference_outline_from_image("D:/img.png", mode="auto")
    """
    payload: Dict[str, Any] = {"image": image, "mode": mode, "invert_luma": bool(invert_luma), "simplify_tol": float(simplify_tol)}
    if threshold is not None:
        payload["threshold"] = float(threshold)
    if bg_color is not None:
        payload["bg_color"] = _ensure_json_list(bg_color) if not isinstance(bg_color, list) else bg_color
    resp = await _blender_request("reference.outline_from_image", payload)
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_reference_reconstruct_from_image(image: str, mode: str = "auto", threshold: Optional[float] = None) -> str:
    """Reconstrucción basada en imagen (usa outline_from_image internamente).

    Ejemplo: blender_reference_reconstruct_from_image("D:/img.png")
    """
    payload: Dict[str, Any] = {"image": image, "mode": mode}
    if threshold is not None:
        payload["threshold"] = float(threshold)
    resp = await _blender_request("reference.reconstruct_from_image", payload)
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_reference_reconstruct_from_alpha(name: str, image: str, view: str = "front", thickness: float = 0.2, threshold: float = 0.5, simplify_tol: float = 2.0) -> str:
    """Reconstruye un sólido extruido a partir de la silueta de una imagen.

    Ejemplo: blender_reference_reconstruct_from_alpha("FromAlpha", "D:/img.png", view="front", thickness=0.2)
    """
    payload = {
        "name": name,
        "image": image,
        "view": view,
        "thickness": float(thickness),
        "threshold": float(threshold),
        "simplify_tol": float(simplify_tol),
    }
    resp = await _blender_request("reference.reconstruct_from_alpha", payload)
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_reference_snap_silhouette_to_blueprint(
    object_name: str,
    view: str,
    image: Optional[str] = None,
    threshold: float = 0.5,
    max_iters: int = 8,
    step: float = 0.02,
    smooth_lambda: float = 0.25,
    smooth_iters: int = 1,
    mode: str = "VERTEX",
) -> str:
    """Ajusta la silueta del objeto a la blueprint por iteraciones.

    Ejemplo: blender_reference_snap_silhouette_to_blueprint("Cube", view="front", threshold=0.5)
    """
    payload: Dict[str, Any] = {
        "object": object_name,
        "view": view,
        "threshold": float(threshold),
        "max_iters": int(max_iters),
        "step": float(step),
        "smooth_lambda": float(smooth_lambda),
        "smooth_iters": int(smooth_iters),
        "mode": mode,
    }
    if image is not None:
        payload["image"] = image
    resp = await _blender_request("reference.snap_silhouette_to_blueprint", payload)
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_selection_by_angle(object_name: str, seed_faces: Any, max_angle: float = 0.349) -> str:
    """Crea una selección creciendo por ángulo de normales desde caras semilla.

    Ejemplo: blender_selection_by_angle("Cube", seed_faces=[0], max_angle=0.3)
    """
    payload = {"object": object_name, "seed_faces": _ensure_json_list(seed_faces) if not isinstance(seed_faces, list) else seed_faces, "max_angle": float(max_angle)}
    resp = await _blender_request("selection.by_angle", payload)
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_proc_terrain(width: float = 50.0, depth: float = 50.0, resolution: int = 128, seed: int = 0, amplitude: float = 5.0, lacunarity: float = 2.0, gain: float = 0.5) -> str:
    """Genera un terreno procedural por ruido fBm (posible tiling para resoluciones altas).

    Ejemplo: blender_proc_terrain(50, 50, 128)
    """
    payload = {
        "width": float(width),
        "depth": float(depth),
        "resolution": int(resolution),
        "seed": int(seed),
        "amplitude": float(amplitude),
        "lacunarity": float(lacunarity),
        "gain": float(gain),
    }
    resp = await _blender_request("proc.terrain", payload)
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_proc_building(
    floors: int = 5,
    bays: int = 4,
    bay_width: float = 3.0,
    floor_height: float = 3.0,
    depth: float = 6.0,
    wall_thickness: float = 0.2,
    window_w: float = 1.2,
    window_h: float = 1.2,
    seed: int = 0,
) -> str:
    """Genera envolvente de edificio con huecos de ventanas (booleanos).

    Ejemplo: blender_proc_building(floors=6, bays=5)
    """
    payload = {
        "floors": int(floors),
        "bays": int(bays),
        "bay_width": float(bay_width),
        "floor_height": float(floor_height),
        "depth": float(depth),
        "wall_thickness": float(wall_thickness),
        "window_w": float(window_w),
        "window_h": float(window_h),
        "seed": int(seed),
    }
    resp = await _blender_request("proc.building", payload)
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_proc_character_base(scale: float = 1.0, proportions_json: Any = None, symmetry_axis: str = "X", thickness: float = 0.02) -> str:
    """Genera personaje base (Skin+Mirror+Subsurf) desde esqueleto de aristas.

    Ejemplo: blender_proc_character_base(scale=1.0, proportions_json={"torso_len":1.2})
    """
    payload: Dict[str, Any] = {"scale": float(scale), "symmetry_axis": symmetry_axis, "thickness": float(thickness)}
    if proportions_json is not None:
        payload["proportions"] = _ensure_json_obj(proportions_json) if not isinstance(proportions_json, dict) else proportions_json
    resp = await _blender_request("proc.character_base", payload)
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_snapshot_capture_view(
    view: str = "front",
    width: int = 768,
    height: int = 768,
    perspective: bool = False,
) -> str:
    """Alias explícito al comando "helpers.snapshot.capture_view".

    Ejemplo: blender_snapshot_capture_view(view="front", width=512, height=512)
    """
    payload = {"view": view, "width": int(width), "height": int(height), "perspective": bool(perspective)}
    resp = await _blender_request("helpers.snapshot.capture_view", payload)
    return json.dumps(resp, indent=2, ensure_ascii=False)


@mcp.tool()
async def blender_mod_apply(object_name: str, name: str) -> str:
    """Aplica un modificador por nombre (usa malla evaluada y limpia la pila hasta ese modificador).

    Ejemplo: blender_mod_apply("Cube", name="Subsurf")
    """
    payload = {"object": object_name, "name": name}
    resp = await _blender_request("mod.apply", payload)
    return json.dumps(resp, indent=2, ensure_ascii=False)



# ---------------------------------------------------------------------
# Entrada principal: stdio (necesario para Gemini CLI)
# ---------------------------------------------------------------------
if __name__ == "__main__":
    # mcp.run() usa stdio por defecto.
    # Ejecuta este archivo con 'python -u' y/o PYTHONUNBUFFERED=1 para evitar delays de buffer.
    _acquire_single_instance_or_exit()
    log.info("Arrancando servidor MCP 'unity_editor'%s. URL puente Unity: %s", " (dummy)" if _TESTMODE else "", MCP_SERVER_URL)
    mcp.run()
