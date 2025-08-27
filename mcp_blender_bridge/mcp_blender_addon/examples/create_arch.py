import asyncio
import json
import time
import websockets
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import websocket_server as ws

ARCH_CODE = '''
import bpy

# Crea dos pilares
bpy.ops.mesh.primitive_cube_add(size=1, location=(-1, 0, 0.5))
pillar1 = bpy.context.active_object
bpy.ops.mesh.primitive_cube_add(size=1, location=(1, 0, 0.5))
pillar2 = bpy.context.active_object

# Crea el arco superior
bpy.ops.mesh.primitive_cylinder_add(radius=1.2, depth=1, location=(0, 0, 1))
arch_top = bpy.context.active_object

# Une las piezas en un solo objeto
bpy.ops.object.select_all(action='DESELECT')
pillar1.select_set(True)
pillar2.select_set(True)
arch_top.select_set(True)
bpy.context.view_layer.objects.active = pillar1
bpy.ops.object.join()
'''

async def main():
    async with websockets.connect("ws://127.0.0.1:8002") as websocket:
        await websocket.send(json.dumps({"command": "execute_python", "params": {"code": ARCH_CODE}}))
        print(await websocket.recv())

if __name__ == "__main__":
    ws.start_server()
    time.sleep(0.1)
    asyncio.get_event_loop().run_until_complete(main())
    ws.stop_server()
