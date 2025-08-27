# mcp_blender_bridge/mcp_blender_addon/websocket_server.py
# Compatible con Blender 2.79 (Python 3.5)

import asyncio
import threading
import json
import os

# Importa bpy si se ejecuta dentro de Blender; si no, usa stubs
try:  # pragma: no cover - dependencia de Blender
    import bpy  # type: ignore
except Exception:
    bpy = None

try:
    import websockets  # usa websockets==7.0 para Py3.5
except Exception as ex:  # pragma: no cover
    print("No se pudo importar 'websockets': {0}".format(ex))
    websockets = None


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
GENERATED_DIR = os.path.join(BASE_DIR, "unity_project", "Assets", "Generated")

server_thread = None
loop = None
server = None


def create_cube(name="Cube", location=(0, 0, 0)):
    """Crea un cubo usando bpy o se comporta como stub si no hay Blender."""
    if bpy is None:  # pragma: no cover
        print("bpy no disponible: create_cube es un stub")
        return name
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.active_object
    obj.name = name
    return obj.name


def create_plane(name="Plane", location=(0, 0, 0)):
    """Crea un plano."""
    if bpy is None:  # pragma: no cover
        print("bpy no disponible: create_plane es un stub")
        return name
    bpy.ops.mesh.primitive_plane_add(location=location)
    obj = bpy.context.active_object
    obj.name = name
    return obj.name


def create_light(name="Light", light_type="POINT", location=(0, 0, 0)):
    """Crea una luz del tipo indicado."""
    if bpy is None:  # pragma: no cover
        print("bpy no disponible: create_light es un stub")
        return name
    bpy.ops.object.light_add(type=light_type, location=location)
    obj = bpy.context.active_object
    obj.name = name
    return obj.name


def apply_transform(name, translation=None, rotation=None, scale=None):
    """Aplica transformaciones a un objeto existente."""
    if bpy is None:  # pragma: no cover
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
    """Exporta la escena actual como FBX en la carpeta compartida."""
    if bpy is None:  # pragma: no cover
        print("bpy no disponible: export_fbx es un stub")
        return path
    full_path = os.path.join(GENERATED_DIR, path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    bpy.ops.export_scene.fbx(filepath=full_path)
    return full_path


async def handler(websocket, path=None):
    """Maneja comandos JSON vía WebSocket (compat. Py3.5)."""
    print("Cliente de WebSocket conectado.")
    try:
        while True:
            message = await websocket.recv()
            if message is None:
                break

            print("Mensaje recibido: {0}".format(message))
            try:
                data = json.loads(message)
            except Exception:
                data = {"command": "echo", "message": message}

            cmd = data.get("command")
            params = data.get("params", {})

            try:
                if cmd == "create_cube":
                    obj_name = create_cube(**params)
                    ack = {"status": "ok", "object": obj_name}
                elif cmd == "create_plane":
                    obj_name = create_plane(**params)
                    ack = {"status": "ok", "object": obj_name}
                elif cmd == "create_light":
                    obj_name = create_light(**params)
                    ack = {"status": "ok", "object": obj_name}
                elif cmd == "export_fbx":
                    exported = export_fbx(**params)
                    ack = {"status": "ok", "path": exported}
                elif cmd == "transform":
                    success = apply_transform(**params)
                    ack = {"status": "ok" if success else "error"}
                else:
                    ack = {"status": "ok", "echo": data}
            except Exception as exc:  # pragma: no cover
                ack = {"status": "error", "message": str(exc)}

            await websocket.send(json.dumps(ack))
    except Exception as e:
        print("Excepción en handler: {0}".format(e))
    finally:
        print("Cliente de WebSocket desconectado.")


def run_server():
    """Arranca el servidor en un bucle propio de asyncio (hilo dedicado)."""
    global loop, server
    if websockets is None:
        print("El módulo 'websockets' no está disponible. Instálalo (websockets==7.0).")
        return

    async def _serve():
        return await websockets.serve(handler, "127.0.0.1", 8002)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        server = loop.run_until_complete(_serve())
        print("Servidor WebSocket iniciado en 127.0.0.1:8002")
        loop.run_forever()
    except Exception as e:
        print("Error al iniciar/ejecutar el servidor: {0}".format(e))
    finally:
        try:
            if server is not None:
                server.close()
                loop.run_until_complete(server.wait_closed())
        except Exception as e:
            print("Error cerrando el servidor: {0}".format(e))
        try:
            loop.close()
        except Exception:
            pass
        print("Bucle de eventos detenido.")


def start_server():
    """Lanza el servidor en segundo plano (idempotente)."""
    global server_thread
    if server_thread is None or not server_thread.is_alive():
        server_thread = threading.Thread(target=run_server)
        server_thread.daemon = True
        server_thread.start()
        print("Hilo del servidor WebSocket iniciado.")


def stop_server():
    """Detiene el servidor y el hilo."""
    global server_thread, loop
    if loop is not None:
        try:
            loop.call_soon_threadsafe(loop.stop)
        except Exception:
            pass
    if server_thread is not None:
        try:
            server_thread.join(timeout=2.0)
        except Exception:
            pass
    server_thread = None
