MCP Blender Add-on (WS Scaffold)
================================

Minimal, dependency-free scaffold for a Blender 4.5 add-on exposing a JSON-over-WebSocket command server with a simple command registry and an executor to marshal Blender API calls to the main thread.

Folder structure
----------------
- `mcp_blender_addon/` — Add-on package
  - `__init__.py` — add-on entry; starts WS server on enable
  - `websocket_server.py` — tiny stdlib WS server (RFC6455 subset)
  - `server/` — infrastructure
    - `registry.py` — command registry/dispatcher
    - `executor.py` — main-thread executor using `bpy.app.timers`
    - `context.py` — lightweight app context
    - `utils.py` — JSON helpers and responses
    - `logging.py` — basic logger setup
  - `commands/` — sample command namespaces
    - `modeling.py`, `topology.py`, `normals.py`
  - `tests/`
    - `smoke_client.py` — stdlib WS client for smoke testing

Requirements
------------
- Blender 4.5 (Python 3.10+ runtime)
- No external Python dependencies

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
- Request: `{ "command": "namespace.action", "params": { ... } }`
- Response (success): `{ "status": "ok", "result": { ... } }`
- Response (error): `{ "status": "error", "error": "message", "code": "optional" }`

Built-in Commands (examples)
----------------------------
- `server.ping` → `{ "pong": true }`
- `modeling.echo` → echoes provided params
- `modeling.get_version` → Blender version (if running in Blender)
- `topology.count_mesh_objects` → counts mesh objects (runs via executor)
- `normals.recalculate_selected` → recalculates normals for selected mesh objects (via executor)

Smoke Test
----------
After enabling the add-on (server listening), run from this repo root:

```
python -m mcp_blender_addon.tests.smoke_client --host 127.0.0.1 --port 8765 --command server.ping
```

Expected output (example):

```
{"status": "ok", "result": {"pong": true}}
```

You can send other commands, e.g.:

```
python -m mcp_blender_addon.tests.smoke_client --command modeling.echo --params '{"hello":"world"}'
```

Executor Notes
--------------
- Blender API interactions must occur on the main thread.
- The `Executor` queues tasks and executes them via `bpy.app.timers`.
- Command handlers that need Blender should call through the executor (see `topology.py`, `normals.py`).

Development Tips
----------------
- Keep commands side-effect free unless necessary; always route bpy/bmesh via the executor.
- Avoid external libs to keep compatibility with Blender’s Python.
