from __future__ import print_function
import asyncio
import threading
import json

try:
    import websockets  # Asegúrate de instalar websockets==7.0 para Py3.5
except Exception as ex:
    print("No se pudo importar 'websockets': {0}".format(ex))
    websockets = None

server_thread = None
loop = None
server = None

@asyncio.coroutine
def handler(websocket, path):
    print("Cliente de WebSocket conectado.")
    try:
        while True:
            message = yield from websocket.recv()
            if message is None:
                break

            print("Mensaje recibido: {0}".format(message))
            try:
                data = json.loads(message)
            except Exception:
                data = {"message": message}

            ack = {"status": "ok", "echo": data}
            yield from websocket.send(json.dumps(ack))
    except Exception as e:
        print("Excepción en handler: {0}".format(e))
    finally:
        print("Cliente de WebSocket desconectado.")

def run_server():
    global loop, server
    if websockets is None:
        print("El módulo 'websockets' no está disponible. Instálalo (websockets==7.0).")
        return

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        server = loop.run_until_complete(websockets.serve(handler, "127.0.0.1", 8002))
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
    global server_thread
    if server_thread is None or not server_thread.is_alive():
        server_thread = threading.Thread(target=run_server)
        server_thread.daemon = True
        server_thread.start()
        print("Hilo del servidor WebSocket iniciado.")

def stop_server():
    global server_thread, loop, server
    try:
        if loop is not None and loop.is_running():
            # Cerrar el servidor y luego parar el loop de forma thread-safe
            def _stop():
                try:
                    if server is not None:
                        server.close()
                except Exception as e:
                    print("Error al cerrar el servidor: {0}".format(e))
                try:
                    loop.stop()
                except Exception as e:
                    print("Error al parar el loop: {0}".format(e))

            loop.call_soon_threadsafe(_stop)

            if server_thread is not None:
                server_thread.join(timeout=2.0)
                server_thread = None
        print("Servidor WebSocket detenido.")
    finally:
        server = None
        loop = None
