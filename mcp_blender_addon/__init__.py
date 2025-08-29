"""
Blender add-on scaffold for a minimal JSON-over-WebSocket command server.

- Python 3.10+ compatible, no external deps.
- All bpy/bmesh usages must go through executor.
"""

from __future__ import annotations

bl_info = {
    "name": "MCP Blender Add-on (WS Scaffold)",
    "author": "AI GameDev Pipeline",
    "version": (0, 1, 0),
    "blender": (4, 5, 0),
    "location": "",
    "description": "Minimal WebSocket JSON command server + command registry",
    "warning": "",
    "doc_url": "",
    "category": "System",
}

import threading

try:
    import bpy  # type: ignore
except Exception:  # pragma: no cover - outside Blender
    bpy = None  # type: ignore

from .server.logging import get_logger
from .server.executor import Executor
from . import websocket_server

_log = get_logger(__name__)

# Singletons for this add-on session
_executor: Executor | None = None
_server: websocket_server.WebSocketServer | None = None


def _ensure_singletons():
    global _executor
    if _executor is None:
        _executor = Executor()


def register():
    """Blender entry point when enabling the add-on."""
    _ensure_singletons()
    assert _executor

    # Initialize executor consumer if in Blender
    if bpy is not None:
        _executor.start()

    # Trigger autoregistration of commands via decorators
    from . import commands  # noqa: F401

    # Register Blender UI (preferences, operators, panel)
    if bpy is not None:
        _register_ui()


def unregister():
    """Blender entry point when disabling the add-on."""
    global _server, _executor
    try:
        if _server is not None:
            _server.stop()
            _server = None
    finally:
        if bpy is not None:
            _unregister_ui()
        if _executor is not None:
            _executor.stop()


# --- Server control helpers ---

def start_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    global _server
    _ensure_singletons()
    assert _executor
    if _server is not None:
        _log.info("Server already running at ws://%s:%d", _server.host, _server.port)
        return
    _server = websocket_server.WebSocketServer(host=host, port=port, registry=None, executor=_executor)
    _server.start()
    _log.info("WebSocket server started on ws://%s:%d", host, port)


def stop_server() -> None:
    global _server
    if _server is None:
        return
    try:
        _server.stop()
        _log.info("WebSocket server stopped")
    finally:
        _server = None


# --- Blender UI (only defined when bpy is available) ---

if bpy is not None:
    import typing as _typing  # noqa: F401
    from bpy.props import StringProperty, IntProperty  # type: ignore

    class MCP_AddonPreferences(bpy.types.AddonPreferences):  # type: ignore
        bl_idname = __package__

        host: StringProperty(name="Host", default="127.0.0.1")  # type: ignore
        port: IntProperty(name="Port", default=8765, min=1, max=65535)  # type: ignore

        def draw(self, context):  # type: ignore
            layout = self.layout
            layout.prop(self, "host")
            layout.prop(self, "port")

    class MCP_OT_ServerStart(bpy.types.Operator):  # type: ignore
        bl_idname = "mcp.server_start"
        bl_label = "Start MCP Server"
        bl_description = "Start the MCP WebSocket server"
        bl_options = {"REGISTER"}

        def execute(self, context):  # type: ignore
            try:
                addon = bpy.context.preferences.addons.get(__package__)
                prefs = addon.preferences if addon else None
                host = getattr(prefs, "host", "127.0.0.1")
                port = int(getattr(prefs, "port", 8765))
                start_server(host, port)
                self.report({"INFO"}, f"Server started at ws://{host}:{port}")
                return {"FINISHED"}
            except Exception as e:  # noqa: BLE001
                self.report({"ERROR"}, str(e))
                return {"CANCELLED"}

    class MCP_OT_ServerStop(bpy.types.Operator):  # type: ignore
        bl_idname = "mcp.server_stop"
        bl_label = "Stop MCP Server"
        bl_description = "Stop the MCP WebSocket server"
        bl_options = {"REGISTER"}

        def execute(self, context):  # type: ignore
            try:
                stop_server()
                self.report({"INFO"}, "Server stopped")
                return {"FINISHED"}
            except Exception as e:  # noqa: BLE001
                self.report({"ERROR"}, str(e))
                return {"CANCELLED"}

    class MCP_PT_ServerPanel(bpy.types.Panel):  # type: ignore
        bl_label = "MCP Server"
        bl_idname = "MCP_PT_server_panel"
        bl_space_type = "VIEW_3D"
        bl_region_type = "UI"
        bl_category = "MCP"

        def draw(self, context):  # type: ignore
            layout = self.layout
            addon = bpy.context.preferences.addons.get(__package__)
            prefs = addon.preferences if addon else None
            host = getattr(prefs, "host", "127.0.0.1")
            port = int(getattr(prefs, "port", 8765))

            running = _server is not None
            row = layout.row()
            row.label(text=f"Status: {'Running' if running else 'Stopped'}")
            layout.separator()
            layout.prop(prefs, "host") if prefs else None
            layout.prop(prefs, "port") if prefs else None
            layout.separator()
            row = layout.row()
            row.operator("mcp.server_start", text="Start", icon="PLAY")
            row.operator("mcp.server_stop", text="Stop", icon="PAUSE")

    _UI_CLASSES = (
        MCP_AddonPreferences,
        MCP_OT_ServerStart,
        MCP_OT_ServerStop,
        MCP_PT_ServerPanel,
    )

    def _register_ui() -> None:
        for cls in _UI_CLASSES:
            try:
                bpy.utils.register_class(cls)  # type: ignore[attr-defined]
            except Exception:
                pass

    def _unregister_ui() -> None:
        for cls in reversed(_UI_CLASSES):
            try:
                bpy.utils.unregister_class(cls)  # type: ignore[attr-defined]
            except Exception:
                pass
else:
    def _register_ui() -> None:  # type: ignore
        return

    def _unregister_ui() -> None:  # type: ignore
        return
