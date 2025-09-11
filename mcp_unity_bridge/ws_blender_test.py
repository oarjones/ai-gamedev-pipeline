# ws_blender_test.py
import asyncio
import json

import websockets  # pip install websockets==10.* o 11.* (en tu Python normal)
try:
    from src.config_manager import ConfigManager  # type: ignore
except Exception:
    ConfigManager = None  # type: ignore

if ConfigManager is not None:
    _cfg = ConfigManager().get()
    URI = f"ws://{_cfg.servers.blender_addon.host}:{_cfg.servers.blender_addon.port}"
    _repo_root = ConfigManager().get_repo_root()
else:
    URI = "ws://127.0.0.1:8002"
    from pathlib import Path
    _repo_root = Path(__file__).resolve().parents[1]

EXEC_CODE = """import bpy
# Limpia la escena
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()
# Crea el cubo
bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
"""


from pathlib import Path
EXPORT_PATH = str((_cfg.paths.blender_export if ConfigManager is not None else (_repo_root / "unity_project" / "Assets" / "Generated")) / "test_cube.fbx")
NAVE_PATH = str(_repo_root / "mcp_unity_bridge" / "nave.py")

async def main():
    print("Conectando a", URI)
    async with websockets.connect(URI, ping_interval=20, ping_timeout=20) as ws:
        # 1) execute_python
        msg1 = {"command": "execute_python", "params": {"code": EXEC_CODE}}
        await ws.send(json.dumps(msg1))
        print(">> enviado execute_python")
        resp1 = await asyncio.wait_for(ws.recv(), timeout=30)
        print("<< respuesta execute_python:", resp1)


        # Mantener vivo un poco y luego cerrar
        await asyncio.sleep(1)
        print("Cerrando conexión.")

if __name__ == "__main__":
    asyncio.run(main())
