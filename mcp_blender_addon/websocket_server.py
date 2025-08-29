from __future__ import annotations

import asyncio
import json
import threading
from typing import Any, Callable, Dict, Optional

from .server.logging import get_logger
from .server.executor import MCP_MAX_TASKS

_log = get_logger(__name__)

# Provided by addon at runtime to enqueue commands
_enqueue: Optional[Callable[[str, Dict[str, Any]], Any]] = None

# Server loop/thread handles
_loop: Optional[asyncio.AbstractEventLoop] = None
_server: Optional[asyncio.AbstractServer] = None
_thread: Optional[threading.Thread] = None
_stopping = threading.Event()


def set_enqueue(fn: Callable[[str, Dict[str, Any]], Any]) -> None:
    global _enqueue
    _enqueue = fn


def start_server(host: str, port: int) -> None:
    global _thread
    if _thread and _thread.is_alive():
        _log.info("WS server already running on ws://%s:%d", host, port)
        return
    _stopping.clear()
    _thread = threading.Thread(target=_run_loop, args=(host, port), name="WS-Server", daemon=True)
    _thread.start()


def stop_server() -> None:
    global _loop, _server, _thread
    _stopping.set()
    if _loop and _server:
        try:
            fut = asyncio.run_coroutine_threadsafe(_shutdown(), _loop)
            fut.result(timeout=2.0)
        except Exception:
            pass
    if _thread:
        _thread.join(timeout=2.0)
    _loop = None
    _server = None
    _thread = None


def _run_loop(host: str, port: int) -> None:
    try:
        import websockets
    except Exception as e:  # pragma: no cover - dependency missing
        _log.error("websockets library not available: %s", e)
        return

    async def handler(ws):
        peer = getattr(ws, "remote_address", ("?", 0))
        _log.info("WS connected: %s", peer)
        try:
            async for raw in ws:
                resp = await _handle_message(raw)
                await ws.send(json.dumps(resp))
        except Exception as e:
            _log.info("WS connection closed: %s", e)

    async def main():
        nonlocal host, port
        srv = await websockets.serve(handler, host, port, ping_interval=20, ping_timeout=20, max_size=8 * 1024 * 1024)
        _log.info("Listening on ws://%s:%d", host, port)
        return srv

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    global _loop, _server
    _loop = loop
    _server = loop.run_until_complete(main())
    try:
        loop.run_until_complete(_wait_for_stop())
    finally:
        loop.run_until_complete(_shutdown())
        loop.close()


async def _wait_for_stop():
    while not _stopping.is_set():
        await asyncio.sleep(0.1)


async def _shutdown():
    global _server
    try:
        if _server:
            _server.close()
            await _server.wait_closed()
    except Exception:
        pass


async def _handle_message(raw: str) -> Dict[str, Any]:
    # Validate JSON
    try:
        data = json.loads(raw)
    except Exception as e:
        return {"status": "error", "tool": "server", "message": f"invalid JSON: {e}", "trace": ""}

    if isinstance(data, dict) and data.get("identify"):
        try:
            import bpy  # type: ignore
            blender_version = tuple(getattr(bpy.app, "version", (0, 0, 0)))  # type: ignore
        except Exception:
            blender_version = None
        try:
            import websockets
            ws_version = getattr(websockets, "__version__", "?")
        except Exception:
            ws_version = "?"
        return {
            "status": "ok",
            "result": {
                "blender_version": blender_version,
                "ws_version": ws_version,
                "module": "mcp_blender_addon",
            },
        }

    if not isinstance(data, dict):
        return {"status": "error", "tool": "server", "message": "invalid message (must be object)", "trace": ""}

    cmd = data.get("command")
    params = data.get("params", {})
    if not isinstance(cmd, str) or not isinstance(params, dict):
        return {"status": "error", "tool": "server", "message": "invalid command payload", "trace": ""}

    # Backpressure: external check if queue is beyond capacity
    if _enqueue is None:
        return {"status": "error", "tool": "server", "message": "server not ready", "trace": ""}

    try:
        exec_obj = getattr(_enqueue, "__self__", None)
        if exec_obj is not None and hasattr(exec_obj, "qsize") and hasattr(exec_obj, "capacity"):
            if exec_obj.qsize() >= exec_obj.capacity():
                return {"status": "error", "tool": "executor", "message": "server busy", "trace": ""}
    except Exception:
        pass

    # Enqueue and wait without blocking the event loop
    task = _enqueue(cmd, params)
    loop = asyncio.get_running_loop()
    try:
        payload = await asyncio.wait_for(loop.run_in_executor(None, task.wait, 10.0), timeout=10.5)
        return payload
    except asyncio.TimeoutError:
        return {"status": "error", "tool": "executor", "message": "timeout", "trace": ""}
