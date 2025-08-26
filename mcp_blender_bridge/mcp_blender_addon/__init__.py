# __init__.py
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


try:
    # Importación relativa: carga el módulo que está junto a este __init__.py
    from . import websocket_server as ws_server
except ImportError:
    # Fallback por si el paquete no se carga como paquete (instalaciones atípicas)
    sys.path.append(os.path.dirname(__file__))
    import websocket_server as ws_server

def register():
    print("MCP Blender Add-on Habilitado.")
    ws_server.start_server()

def unregister():
    print("MCP Blender Add-on Deshabilitado.")
    ws_server.stop_server()