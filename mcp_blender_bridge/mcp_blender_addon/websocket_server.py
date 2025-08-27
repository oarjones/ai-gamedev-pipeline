# mcp_blender_bridge/mcp_blender_addon/websocket_server.py
# Compatible con Blender 2.79 (Python 3.5) + websockets==7.0

import asyncio
import threading
import json
import os
import importlib
import io
import traceback
from contextlib import redirect_stdout, redirect_stderr

# --- Dependencias de Blender (opcionales si se ejecuta fuera de Blender) ---
try:
    import bpy  # type: ignore
except Exception:
    bpy = None

# --- WebSockets (recomendado websockets==7.0 para Python 3.5) ---
try:
    import websockets  # type: ignore
except Exception as ex:
    print("No se pudo importar 'websockets': {0}".format(ex))
    websockets = None

# Normaliza excepciones de cierre según versión de 'websockets'
if websockets is not None:
    try:
        from websockets.exceptions import ConnectionClosed, ConnectionClosedOK, ConnectionClosedError  # type: ignore
    except Exception:
        try:
            from websockets.exceptions import ConnectionClosed as _CC  # type: ignore
            ConnectionClosed = _CC
        except Exception:
            ConnectionClosed = Exception
        ConnectionClosedOK = ConnectionClosed
        ConnectionClosedError = ConnectionClosed
else:
    class _DummyClosed(Exception):
        pass
    ConnectionClosed = ConnectionClosedOK = ConnectionClosedError = _DummyClosed

# --- Rutas base ---
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
GENERATED_DIR = os.path.join(BASE_DIR, "unity_project", "Assets", "Generated")

# --- Estado del servidor ---
server_thread = None
loop = None
server = None


# =========================
# Utilidades 3D
# =========================

def create_cube(name="Cube", location=(0, 0, 0)):
    if bpy is None:
        print("bpy no disponible: create_cube es un stub")
        return name
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.active_object
    obj.name = name
    return obj.name


def create_plane(name="Plane", location=(0, 0, 0)):
    if bpy is None:
        print("bpy no disponible: create_plane es un stub")
        return name
    bpy.ops.mesh.primitive_plane_add(location=location)
    obj = bpy.context.active_object
    obj.name = name
    return obj.name


def create_light(name="Light", light_type="POINT", location=(0, 0, 0)):
    if bpy is None:
        print("bpy no disponible: create_light es un stub")
        return name
    try:
        if getattr(bpy.app, "version", (2, 80, 0)) < (2, 80, 0):
            bpy.ops.object.lamp_add(type=light_type, location=location)
        else:
            bpy.ops.object.light_add(type=light_type, location=location)
        obj = bpy.context.active_object
        obj.name = name
        return obj.name
    except Exception as exc:
        print("Error creando luz: {0}".format(exc))
        raise


def apply_transform(name, translation=None, rotation=None, scale=None):
    if bpy is None:
        print("bpy no disponible: apply_transform es un stub")
        return True
    obj = bpy.data.objects.get(name)
    if obj is None:
        return False
    if translation is not None:
        obj.location = translation
    if rotation is not None:
        obj.rotation_euler = rotation
    if scale is not None:
        obj.scale = scale
    return True


def export_fbx(path):
    if bpy is None:
        print("bpy no disponible: export_fbx es un stub")
        return path

    if isinstance(path, str):
        path = path.replace("/", os.sep).replace("\\", os.sep)
    else:
        path = "export.fbx"

    if os.path.isabs(path):
        full_path = path
    else:
        full_path = os.path.join(GENERATED_DIR, path)

    try:
        dirpath = os.path.dirname(full_path)
        if dirpath and not os.path.exists(dirpath):
            os.makedirs(dirpath)
        bpy.ops.export_scene.fbx(filepath=full_path)
        return full_path
    except Exception as exc:
        print("Error al exportar FBX: {0}".format(exc))
        raise


def execute_python(code):
    local_env = {"bpy": bpy}
    stdout_io = io.StringIO()
    stderr_io = io.StringIO()
    try:
        with redirect_stdout(stdout_io), redirect_stderr(stderr_io):
            exec(code, local_env, local_env)
    except Exception as exc:
        print("execute_python error: {0}".format(exc))
        traceback.print_exc()
    return stdout_io.getvalue(), stderr_io.getvalue()


def execute_python_file(path):
    if not path:
        raise ValueError("Ruta del script no proporcionada")
    if not os.path.isabs(path):
        path = os.path.join(BASE_DIR, path)
    if not os.path.exists(path):
        raise FileNotFoundError("No existe: {0}".format(path))
    with open(path, "r", encoding="utf-8") as f:
        code = f.read()
    return execute_python(code)


def run_macro(name, **kwargs):
    try:
        module = importlib.import_module(".macros." + name, package=__package__)
    except ImportError:
        return {"status": "error", "error": "Macro '{0}' no encontrado".format(name)}
    if not hasattr(module, "run"):
        return {"status": "error", "error": "Macro '{0}' sin función run".format(name)}
    try:
        result = module.run(**kwargs)
        return {"status": "ok", "result": result}
    except TypeError as exc:
        return {"status": "error", "error": str(exc)}
    except Exception as exc:
        traceback.print_exc()
        return {"status": "error", "error": str(exc)}


# =========================
# Servidor WebSocket (websockets==7.0)
# =========================

async def handler(websocket, path=None):
    print("Cliente de WebSocket conectado.")
    try:
        while True:
            # En websockets 7.0 NO existe 'async for websocket': usar recv()
            try:
                message = await websocket.recv()
            except (ConnectionClosed, ConnectionClosedOK, ConnectionClosedError):
                print("Conexión cerrada de forma normal.")
                break
            except Exception as e:
                print("Excepción en recv(): {0}".format(e))
                traceback.print_exc()
                break

            print("Mensaje recibido: {0}".format(message))

            # Parse defensivo
            try:
                data = json.loads(message)
            except Exception:
                data = {"command": "echo", "message": message}

            cmd = data.get("command")
            params = data.get("params", {}) or {}

            try:
                if cmd == "create_cube":
                    ack = {"status": "ok", "object": create_cube(**params)}
                elif cmd == "create_plane":
                    ack = {"status": "ok", "object": create_plane(**params)}
                elif cmd == "create_light":
                    ack = {"status": "ok", "object": create_light(**params)}
                elif cmd == "export_fbx":
                    ack = {"status": "ok", "path": export_fbx(**params)}
                elif cmd == "transform":
                    ack = {"status": "ok" if apply_transform(**params) else "error"}
                elif cmd == "execute_python":
                    stdout, stderr = execute_python(params.get("code", ""))
                    ack = {"status": "ok", "stdout": stdout, "stderr": stderr}
                elif cmd == "execute_python_file":
                    stdout, stderr = execute_python_file(params.get("path", ""))
                    ack = {"status": "ok", "stdout": stdout, "stderr": stderr}
                elif cmd == "run_macro":
                    ack = run_macro(**params)
                elif cmd == "identify":
                    ack = {
                        "status": "ok",
                        "module_file": __file__,
                        "websockets_version": getattr(websockets, "__version__", "unknown"),
                        "blender_version": getattr(bpy.app, "version", None),
                    }
                else:
                    ack = {"status": "ok", "echo": data}
            except Exception as exc:
                print("[DEBUG] Error procesando comando '{0}': {1}".format(cmd, exc))
                traceback.print_exc()
                ack = {"status": "error", "message": str(exc)}

            # Enviar ACK
            try:
                payload = json.dumps(ack)
            except Exception as exc:
                print("[DEBUG] json.dumps falló: {0}".format(exc))
                traceback.print_exc()
                payload = json.dumps({"status": "error", "message": "json serialization error"})

            try:
                await websocket.send(payload)
            except (ConnectionClosed, ConnectionClosedOK, ConnectionClosedError):
                print("Cliente cerró antes de recibir el ACK (cierre normal).")
                break
            except Exception as exc:
                print("[DEBUG] Excepción durante send(): {0}".format(exc))
                traceback.print_exc()
                break

    except Exception as e:
        print("Excepción en handler: {0}".format(e))
        traceback.print_exc()
    finally:
        print("Cliente de WebSocket desconectado.")


def run_server():
    global loop, server
    if websockets is None:
        print("El módulo 'websockets' no está disponible. Instálalo (websockets==7.0).")
        return

    async def _serve():
        return await websockets.serve(
            handler, "127.0.0.1", 8002,
            ping_interval=20, ping_timeout=20, max_queue=1, close_timeout=0
        )

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        server = loop.run_until_complete(_serve())
        ver = getattr(websockets, "__version__", "unknown")
        print("Servidor WebSocket iniciado en 127.0.0.1:8002 (websockets {0})".format(ver))
        loop.run_forever()
    except Exception as e:
        print("Error al iniciar/ejecutar el servidor: {0}".format(e))
        traceback.print_exc()
    finally:
        try:
            if server is not None:
                server.close()
                loop.run_until_complete(server.wait_closed())
        except Exception as e:
            print("Error cerrando el servidor: {0}".format(e))
            traceback.print_exc()
        try:
            loop.close()
        except Exception:
            pass
        print("Bucle de eventos detenido.")


def start_server():
    global server_thread
    if server_thread is None or not server_thread.is_alive():
        server_thread = threading.Thread(target=run_server)
        server_thread.daemon = True
        server_thread.start()
        print("Hilo del servidor WebSocket iniciado.")


def stop_server():
    global server_thread, loop
    if loop is not None:
        try:
            loop.call_soon_threadsafe(loop.stop)
        except Exception:
            traceback.print_exc()
    if server_thread is not None:
        try:
            server_thread.join(timeout=2.0)
        except Exception:
            traceback.print_exc()
    server_thread = None
