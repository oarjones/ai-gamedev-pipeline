import bpy
import importlib
import os, sys

bl_info = {
    "name": "MCP Blender Add-on",
    "author": "AI GameDev Pipeline Project",
    "version": (0, 0, 1),
    "blender": (2, 79, 0),
    "category": "Development",
    "description": "Provides an interface for the AI GameDev Pipeline to interact with Blender.",
    "location": "MCP > Panel",
    "warning": "",
    "wiki_url": "",
}

def register():
    print("MCP Blender Add-on Habilitado.")
    # Import relativo al paquete del add-on
    from . import websocket_server as ws_server
    # Fuerza recarga para evitar quedar enganchado a una versión antigua
    ws_server = importlib.reload(ws_server)
    ws_server.start_server()

def unregister():
    print("MCP Blender Add-on Deshabilitado.")
    try:
        from . import websocket_server as ws_server
        ws_server.stop_server()
    except Exception:
        pass
