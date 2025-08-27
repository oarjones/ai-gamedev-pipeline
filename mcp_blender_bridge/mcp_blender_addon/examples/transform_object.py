import asyncio
import json
import time
import websockets
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import websocket_server as ws

async def main():
    async with websockets.connect("ws://127.0.0.1:8002") as websocket:
        await websocket.send(json.dumps({"command": "create_cube", "params": {"name": "CubeToTransform"}}))
        print(await websocket.recv())
        await websocket.send(json.dumps({
            "command": "transform",
            "params": {
                "name": "CubeToTransform",
                "translation": [1, 2, 3],
                "rotation": [0, 0, 0],
                "scale": [2, 2, 2]
            }
        }))
        print(await websocket.recv())

if __name__ == "__main__":
    ws.start_server()
    time.sleep(0.1)
    asyncio.get_event_loop().run_until_complete(main())
    ws.stop_server()