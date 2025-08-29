MCP Blender Add-on (WS Scaffold)
================================

Minimal scaffold for a Blender 4.5 add-on exposing a JSON-over-WebSocket command server using `websockets` (asyncio). Commands never execute `bpy` in WS threads; instead, an executor pumps tasks on Blender’s main thread via `bpy.app.timers`.

Folder Structure
----------------
- `mcp_blender_addon/` — Add-on package
  - `__init__.py` — add-on entry; UI to start/stop server
  - `websocket_server.py` — asyncio `websockets` server (no bpy access)
  - `server/` — infrastructure
    - `registry.py` — global command registry + decorators
    - `executor.py` — main-thread pump using `bpy.app.timers`
    - `context.py` — session context + bmesh helpers
    - `utils.py` — JSON helpers
    - `logging.py` — console + rotating file logging
  - `commands/` — tool namespaces
    - `modeling.py`, `topology.py`, `normals.py`
  - `tests/`
    - `smoke_client.py` — stdlib WS client + smoke suite

Requirements
------------
- Blender 4.5 (Python 3.10+ runtime)
- Python package `websockets` available in Blender’s Python

Install & Enable
----------------
1) In Blender, go to `Edit > Preferences > Add-ons`.
2) Click `Install...`, select the project folder (or zip it first), and enable "MCP Blender Add-on (WS Scaffold)".
3) Configure Host/Port under the add-on’s Preferences if needed.

Start/Stop
----------
- Use the 3D View > Sidebar (N) > `MCP` > `MCP Server` panel.
- Click `Start` to launch and `Stop` to shut down. Defaults to `127.0.0.1:8765` unless changed in Preferences.

JSON Contract
-------------
- Identify: `{ "identify": true }` → `{ "status": "ok", "result": { "blender_version": [4,5,0], "ws_version": "...", "module": "mcp_blender_addon" } }`
- Command: `{ "command": "namespace.action", "params": { ... } }`
- Success: `{ "status": "ok", "result": { ... } }`
- Error: `{ "status": "error", "tool": "<component>", "message": "...", "trace": "..." }`

Built-in Tools (examples)
-------------------------
- `server.ping` → `{ "pong": true }`
- `server.list_commands` → list of available command names
- `modeling.create_primitive` → create cube/plane/cylinder via bmesh
- `modeling.extrude_normal` → extrude faces along average normal
- `topology.bevel_edges` → bevel selected edges
- `topology.merge_by_distance` → remove doubles
- `normals.recalc` → recalc normals outward/inward

Smoke Tests
-----------
- Full suite with logs:
  - `python -m mcp_blender_addon.tests.smoke_client --suite smoke`
  - Logs saved under `Generated/logs/YYYYMMDD/` as JSON files per step.
- Single command:
  - `python -m mcp_blender_addon.tests.smoke_client --command server.ping`
  - Identify only: `python -m mcp_blender_addon.tests.smoke_client --identify`

Executor Notes
--------------
- Blender API interactions must occur on the main thread.
- The `Executor` queues tasks and executes them via `bpy.app.timers`.
- Command handlers that need Blender should call through the executor (see `topology.py`, `normals.py`).

Logging
-------
- Console logs go to stdout; a rotating file log is written to:
  - Windows/macOS/Linux: `~/.mcp_blender_addon/logs/addon.log` (1MB x 3 backups)

WebSockets Library
------------------
- The add-on’s WS server uses the `websockets` package. If Blender’s Python lacks it, install into Blender’s Python environment, e.g. (Windows example):
  - `"C:\\Program Files\\Blender Foundation\\Blender 4.5\\4.5\\python\\bin\\python.exe" -m ensurepip`
  - `"...python.exe" -m pip install websockets`
