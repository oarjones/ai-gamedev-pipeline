# ws_blender_full_test.py
# Pruebas integrales del servidor WebSocket de Blender 2.79
# Requiere: pip install websockets==10.* (o 11.*)

import asyncio
import json
import os
from datetime import datetime

import websockets  # cliente moderno; el servidor usa websockets 7.0 internamente

URI = "ws://127.0.0.1:8002"

# --- Config de rutas opcionales para IoU ---
IMAGE_TOP = r""   # p.ej. r"D:\refs\ship_top.png"
IMAGE_SIDE = r""  # p.ej. r"D:\refs\ship_profile.png"

# --- Export de prueba ---
EXPORT_PATH = r"D:\ai-gamedev-pipeline\unity_project\Assets\Generated\test_ws_full.fbx"

# --- Helpers ---------------------------------------------------------------

async def send_cmd(ws, command: str, params: dict = None, label: str = "") -> dict:
    msg = {"command": command, "params": params or {}}
    await ws.send(json.dumps(msg))
    try:
        resp_str = await asyncio.wait_for(ws.recv(), timeout=60)
    except asyncio.TimeoutError:
        print(f"<< ({label or command}) TIMEOUT")
        return {"status": "error", "message": "timeout"}
    try:
        resp = json.loads(resp_str)
    except Exception:
        resp = {"status": "ok", "payload": resp_str}
    tag = label or command
    print(f"<< {tag}: {json.dumps(resp, ensure_ascii=False)}")
    return resp

async def header(title: str):
    print("\n" + "="*80)
    print(f"{title}  [{datetime.now().strftime('%H:%M:%S')}]")
    print("="*80)

def img_path_ok(p: str) -> bool:
    return bool(p and os.path.isabs(p) and os.path.exists(p))

# --- Outline de ejemplo ----------------------------------------------------
OUTLINE_SHIP = [
    [0.00,  1.00],
    [0.22,  0.60],
    [0.38,  0.35],
    [0.46,  0.05],
    [0.40, -0.25],
    [0.24, -0.55],
    [0.10, -0.80],
    [0.00, -0.90]
]

OUTLINE_NOSE = [
    [0.00,  1.05],
    [0.10,  0.95],
    [0.12,  0.85],
    [0.08,  0.75],
    [0.00,  0.70]
]

# --- Limpieza de escena (se hace vía execute_python) -----------------------
EXEC_CLEAR = """import bpy
for obj in list(bpy.data.objects):
    try:
        bpy.data.objects.remove(obj, do_unlink=True)
    except:
        pass
"""

# --- Test principal --------------------------------------------------------
async def main():
    print("Conectando a", URI)
    async with websockets.connect(URI, ping_interval=20, ping_timeout=20) as ws:

        await header("IDENTIFY")
        await send_cmd(ws, "identify")

        await header("EXECUTE_PYTHON - limpiar escena")
        await send_cmd(ws, "execute_python", {"code": EXEC_CLEAR}, "execute_python(clear)")

        await header("CREAR BASES")
        r1 = await send_cmd(ws, "geom.create_base", {
            "name": "Ship",
            "outline": OUTLINE_SHIP,
            "thickness": 0.22,
            "mirror_x": True
        })
        r2 = await send_cmd(ws, "geom.create_base", {
            "name": "Nose",
            "outline": OUTLINE_NOSE,
            "thickness": 0.18,
            "mirror_x": True
        })
        await send_cmd(ws, "mesh.stats", {"object": "Ship"})
        await send_cmd(ws, "mesh.stats", {"object": "Nose"})

        await header("SELECCIÓN + EXTRUSIÓN (nariz Ship)")
        sel_nose = await send_cmd(ws, "select.faces_by_range", {
            "object": "Ship",
            "conds": [{"axis": "y", "min": 0.85}]
        })
        sid = sel_nose.get("selection_id", 0)
        await send_cmd(ws, "edit.extrude_selection", {
            "object": "Ship",
            "selection_id": sid,
            "translate": [0, 0.18, 0],
            "scale_about_center": [0.7, 1, 1],
            "inset": 0.0
        }, "extrude(nose)")

        await header("GROW + SCULPT")
        sel_grow = await send_cmd(ws, "select.grow", {
            "object": "Ship",
            "selection_id": sid,
            "steps": 1
        })
        sid_grow = sel_grow.get("selection_id", 0)
        await send_cmd(ws, "edit.sculpt_selection", {
            "object": "Ship",
            "selection_id": sid_grow,
            "move": [
                {"axis": "z", "fn": "gauss", "center_y": 0.40, "width": 0.28, "amplitude": 0.12}
            ]
        }, "sculpt(gauss canopy)")

        await header("SELECCIÓN LATERAL + EXTRUSIÓN (pods)")
        sel_pods = await send_cmd(ws, "select.faces_by_range", {
            "object": "Ship",
            "conds": [
                {"axis": "y", "min": 0.15, "max": 0.65},
                {"axis": "x", "min": 0.30}
            ]
        })
        sid_pods = sel_pods.get("selection_id", 0)
        await send_cmd(ws, "edit.extrude_selection", {
            "object": "Ship",
            "selection_id": sid_pods,
            "translate": [0.18, 0, 0],
            "scale_about_center": [1, 1, 0.9]
        }, "extrude(pods)")

        await header("SELECCIÓN COLA + EXTRUSIÓN (toberas)")
        sel_tail = await send_cmd(ws, "select.faces_by_range", {
            "object": "Ship",
            "conds": [{"axis": "y", "max": -0.80}]
        })
        sid_tail = sel_tail.get("selection_id", 0)
        await send_cmd(ws, "edit.extrude_selection", {
            "object": "Ship",
            "selection_id": sid_tail,
            "translate": [0, -0.16, 0],
            "inset": 0.02
        }, "extrude(tail)")

        await header("CLEANUP + MIRROR + STATS")
        await send_cmd(ws, "geom.cleanup", {"object": "Ship", "merge_dist": 0.0008, "recalc": True})
        await send_cmd(ws, "geom.mirror_x", {"object": "Ship", "merge_dist": 0.0008})
        await send_cmd(ws, "mesh.stats", {"object": "Ship"})
        await send_cmd(ws, "mesh.validate", {"object": "Ship", "check_self_intersections": False})
        await send_cmd(ws, "mesh.normals_recalc", {"object": "Ship", "ensure_outside": True})

        await header("CURVATURA: seleccionar vértices marcados y mover ligeramente")
        sel_curv = await send_cmd(ws, "select.verts_by_curvature", {
            "object": "Ship",
            "min_curv": 0.10
        })
        sid_curv = sel_curv.get("selection_id", 0)
        await send_cmd(ws, "edit.move_verts", {
            "object": "Ship",
            "selection_id": sid_curv,
            "translate": [0, 0, 0.02],
            "scale_about_center": [1, 1, 1]
        }, "move(verts by curvature)")

        await header("SNAPSHOT / RESTORE")
        snap = await send_cmd(ws, "mesh.snapshot", {"object": "Ship"})
        snap_id = snap.get("snapshot_id", 0)
        # Deformación rápida
        sel_mid = await send_cmd(ws, "select.faces_in_bbox", {
            "object": "Ship",
            "min": [-0.30, -0.10, -0.10],
            "max": [ 0.30,  0.40,  0.10]
        })
        sid_mid = sel_mid.get("selection_id", 0)
        await send_cmd(ws, "edit.move_verts", {
            "object": "Ship",
            "selection_id": sid_mid,
            "translate": [0, 0, 0.05],
            "scale_about_center": [1.05, 1.0, 1.05]
        }, "move(mid bump)")
        await send_cmd(ws, "mesh.restore", {"snapshot_id": snap_id, "object": "Ship"})

        await header("SIMILARIDAD IoU TOP / SIDE / COMBO (opcional)")
        if img_path_ok(IMAGE_TOP):
            await send_cmd(ws, "similarity.iou_top", {
                "object": "Ship",
                "image_path": IMAGE_TOP,
                "res": 256,
                "margin": 0.05,
                "threshold": 0.5
            })
        else:
            print("** Saltando IoU TOP (IMAGE_TOP no configurada o no existe).")
        if img_path_ok(IMAGE_SIDE):
            await send_cmd(ws, "similarity.iou_side", {
                "object": "Ship",
                "image_path": IMAGE_SIDE,
                "res": 256,
                "margin": 0.05,
                "threshold": 0.5
            })
        else:
            print("** Saltando IoU SIDE (IMAGE_SIDE no configurada o no existe).")
        if img_path_ok(IMAGE_TOP) and img_path_ok(IMAGE_SIDE):
            await send_cmd(ws, "similarity.iou_combo", {
                "object": "Ship",
                "image_top": IMAGE_TOP,
                "image_side": IMAGE_SIDE,
                "alpha": 0.6
            })

        await header("MERGE / STITCH (Ship + Nose → Ship_Merged)")
        await send_cmd(ws, "merge.stitch", {
            "object_a": "Ship",
            "object_b": "Nose",
            "out_name": "Ship_Merged",
            "delete": "B_inside_A",   # elimina lo interior de B respecto a A
            "weld_dist": 0.0008
        })
        await send_cmd(ws, "mesh.stats", {"object": "Ship_Merged"})
        await send_cmd(ws, "mesh.validate", {"object": "Ship_Merged", "check_self_intersections": False})
        await send_cmd(ws, "mesh.normals_recalc", {"object": "Ship_Merged", "ensure_outside": True})

        await header("EXPORT FBX (final)")
        await send_cmd(ws, "export_fbx", {"path": EXPORT_PATH})

        await header("LISTO")
        await asyncio.sleep(0.5)

if __name__ == "__main__":
    asyncio.run(main())
