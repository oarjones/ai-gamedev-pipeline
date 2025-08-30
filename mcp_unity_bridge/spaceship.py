# spaceship.py
# Agente IA mínimo para modelar una nave a partir de 3 plantillas (TOP/LEFT/FRONT)
# Requiere que el servidor WS de Blender 2.79 esté corriendo en 127.0.0.1:8002

import asyncio
import json
import argparse
from datetime import datetime
import os
import websockets

URI = "ws://127.0.0.1:8002"

# ==== EDITA ESTAS RUTAS ======================================================
IMAGE_TOP   = r"D:\refs\ship_top.png"    # planta (XY)
IMAGE_LEFT  = r"D:\refs\ship_left.png"   # perfil izquierdo (XZ)
IMAGE_FRONT = r"D:\refs\ship_front.png"  # frontal (YZ)
EXPORT_PATH = r"D:\ai-gamedev-pipeline\unity_project\Assets\Generated\spaceship_auto.fbx"
# =============================================================================

# Parámetros de snap (puedes afinarlos)
SNAP_ITERS = 10
SNAP_STRENGTH = 0.65
SNAP_STEP = 1.0
SNAP_RES = 512

def ts():
    return datetime.now().strftime("%H:%M:%S")

async def send(ws, command, params=None, label=None):
    msg = {"command": command, "params": params or {}}
    await ws.send(json.dumps(msg))
    resp = json.loads(await ws.recv())
    tag = label or command
    print(f"<< {tag}: {json.dumps(resp, ensure_ascii=False)}")
    return resp

def sid_of(resp):
    try:
        return int(resp.get("selection_id", 0))
    except Exception:
        return 0

def have(path):
    return bool(path and os.path.exists(path))


async def get_bbox(ws, obj_name="Ship"):
    r = await send(ws, "mesh.stats", {"object": obj_name})
    bb = r.get("bbox") or {}
    bbmin = bb.get("min") or [-1,-1,-1]
    bbmax = bb.get("max") or [ 1, 1, 1]
    return bbmin, bbmax

def lerp(a, b, t): return a + (b - a) * t


# ------------------------- PASOS / MÉTODOS -----------------------------------

async def p_identify(ws):
    print("\n" + "="*80); print(f"IDENTIFY [{ts()}]"); print("="*80)
    await send(ws, "identify")

async def p_clear(ws):
    print("\n" + "="*80); print(f"LIMPIAR ESCENA [{ts()}]"); print("="*80)
    code = """import bpy
for ob in list(bpy.data.objects):
    try: bpy.data.objects.remove(ob, do_unlink=True)
    except: pass
"""
    await send(ws, "execute_python", {"code": code}, "execute_python(clear)")

async def p_create_base(ws):
    print("\n" + "="*80); print(f"CREAR BASE SIMÉTRICA [{ts()}]"); print("="*80)
    # Base simple; la silueta TOP la ajustaremos con snap.
    outline = [
        [0.00,  1.00],
        [0.20,  0.55],
        [0.34,  0.15],
        [0.36, -0.25],
        [0.24, -0.55],
        [0.10, -0.85],
        [0.00, -0.95],
    ]
    await send(ws, "geom.create_base", {
        "name": "Ship",
        "outline": outline,
        "thickness": 0.18,
        "mirror_x": True
    })
    await send(ws, "mesh.stats", {"object": "Ship"})

async def p_snap_top(ws):
    print("\n" + "="*80); print(f"ENCAGE A TOP (XY) [{ts()}]"); print("="*80)
    if not have(IMAGE_TOP):
        print("** Falta IMAGE_TOP, saltando.")
        return
    sel = await send(ws, "select.faces_in_bbox", {"object":"Ship","min":[-10,-10,-10],"max":[10,10,10]})
    sid = sid_of(sel)
    await send(ws, "edit.snap_to_silhouette", {
        "object": "Ship",
        "selection_id": sid,
        "plane": "XY",
        "image_path": IMAGE_TOP,
        "strength": SNAP_STRENGTH,
        "iterations": SNAP_ITERS,
        "step": SNAP_STEP,
        "res": SNAP_RES,
        "margin": 0.05,
        "threshold": 0.5
    })
    await send(ws, "geom.cleanup", {"object":"Ship","merge_dist":0.0008,"recalc":True})
    await send(ws, "geom.mirror_x", {"object":"Ship","merge_dist":0.0008})

async def p_snap_front(ws):
    print("\n" + "="*80); print(f"ENCAGE A FRONT (YZ) — SLICE SAFE [{ts()}]"); print("="*80)
    if not have(IMAGE_FRONT):
        print("** Falta IMAGE_FRONT, saltando.")
        return

    # bbox para dividir la malla en celdas YZ (3x3)
    (xmin, ymin, zmin), (xmax, ymax, zmax) = await get_bbox(ws, "Ship")

    # hacemos 2 pasadas con fuerza/iteraciones bajas
    passes = [
        {"iters": 3, "strength": 0.45},
        {"iters": 4, "strength": 0.55},
    ]

    for pconf in passes:
        iters = pconf["iters"]
        strength = pconf["strength"]

        # cortes en Y y Z (3 celdas por eje)
        y_edges = [ymin, lerp(ymin, ymax, 1/3.0), lerp(ymin, ymax, 2/3.0), ymax]
        z_edges = [zmin, lerp(zmin, zmax, 1/3.0), lerp(zmin, zmax, 2/3.0), zmax]

        for yi in range(3):
            for zi in range(3):
                y0, y1 = y_edges[yi], y_edges[yi+1]
                z0, z1 = z_edges[zi], z_edges[zi+1]
                # caja amplia en X (no importa el espesor para la selección)
                box_min = [xmin - 1.0, min(y0, y1), min(z0, z1)]
                box_max = [xmax + 1.0, max(y0, y1), max(z0, z1)]

                sel = await send(ws, "select.faces_in_bbox", {"object":"Ship","min":box_min,"max":box_max},
                                 f"slice yz[{yi},{zi}] select")
                sid = sid_of(sel)
                if sid == 0 or int(sel.get("count", 0)) == 0:
                    continue

                # Snap en esta celda con poquitas iteraciones y fuerza moderada
                resp = await send(ws, "edit.snap_to_silhouette", {
                    "object": "Ship",
                    "selection_id": sid,
                    "plane": "YZ",
                    "image_path": IMAGE_FRONT,
                    "strength": strength,
                    "iterations": iters,
                    "step": 1.0,
                    "res": min(SNAP_RES, 384),  # algo más bajo por estabilidad
                    "margin": 0.05,
                    "threshold": 0.5
                }, f"slice yz[{yi},{zi}] snap")
                if resp.get("status") != "ok":
                    print("** Snap slice devolvió error, continuo con la siguiente")

        # Pequeña validación entre pasadas (sin merges agresivos)
        await send(ws, "mesh.validate", {"object":"Ship","check_self_intersections": False})
        await send(ws, "mesh.normals_recalc", {"object":"Ship","ensure_outside": True})

    print("FRONT snap por rebanadas completado.")


async def p_snap_side(ws):
    print("\n" + "="*80); print(f"ENCAGE A LEFT/SIDE (XZ) [{ts()}]"); print("="*80)
    if not have(IMAGE_LEFT):
        print("** Falta IMAGE_LEFT, saltando.")
        return
    sel = await send(ws, "select.faces_in_bbox", {"object":"Ship","min":[-10,-10,-10],"max":[10,10,10]})
    sid = sid_of(sel)
    await send(ws, "edit.snap_to_silhouette", {
        "object": "Ship",
        "selection_id": sid,
        "plane": "XZ",
        "image_path": IMAGE_LEFT,
        "strength": SNAP_STRENGTH,
        "iterations": SNAP_ITERS,
        "step": SNAP_STEP,
        "res": SNAP_RES,
        "margin": 0.05,
        "threshold": 0.5
    })

async def p_refine_and_bevel(ws):
    print("\n" + "="*80); print(f"LIMPIEZA + BEVEL LIGERO [{ts()}]"); print("="*80)
    await send(ws, "geom.cleanup", {"object":"Ship","merge_dist":0.0008,"recalc":True})

    # Validar antes de biselar
    v = await send(ws, "mesh.validate", {"object":"Ship","check_self_intersections": False})
    # si hay agujeros, intenta rellenar; si hay muchas non-manifold, suaviza la topología
    if int(v.get("non_manifold_edges", 0)) > 0:
        await send(ws, "mesh.fill_holes", {"object":"Ship"})
        await send(ws, "geom.cleanup", {"object":"Ship","merge_dist":0.0008,"recalc":True})

    # Intento 1 (normal)
    r = await send(ws, "mesh.bevel", {
        "object":"Ship",
        "selection_id": None,
        "offset": 0.008,
        "segments": 2,
        "profile": 0.7,
        "clamp": True,
        "auto_sharp_angle": 35.0
    })
    if r.get("status") != "ok":
        print("** bevel normal falló, probando fallback suave")
        # Intento 2 (más conservador)
        await send(ws, "mesh.bevel", {
            "object":"Ship",
            "selection_id": None,
            "offset": 0.004,
            "segments": 1,
            "profile": 0.7,
            "clamp": True,
            "auto_sharp_angle": 30.0
        })

    await send(ws, "mesh.normals_recalc", {"object":"Ship","ensure_outside":True})


async def p_densify_coarse(ws):
    print("\n" + "="*80); print(f"DENSIFICAR (subdivide global) [{ts()}]"); print("="*80)
    code = (
        "import bpy, bmesh\n"
        "name='Ship'\n"
        "obj=bpy.data.objects.get(name)\n"
        "if obj:\n"
        "    me=obj.data\n"
        "    bm=bmesh.new(); bm.from_mesh(me)\n"
        "    bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table()\n"
        "    edges=[e for e in bm.edges if (e.verts[0].co - e.verts[1].co).length>1e-6]\n"
        "    bmesh.ops.subdivide_edges(bm, edges=edges, cuts=1, use_grid_fill=False, smooth=0.0)\n"
        "    # Limpieza mínima (¡no merges grandes!)\n"
        "    try: bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-7)\n"
        "    except: pass\n"
        "    bm.to_mesh(me); me.update()\n"
    )
    await send(ws, "execute_python", {"code": code}, "execute_python(subdivide global)")
    await send(ws, "mesh.stats", {"object":"Ship"})




async def p_densify_targeted(ws):
    print("\n" + "="*80); print(f"DENSIFICAR DIRIGIDO (loops & rings) [{ts()}]"); print("="*80)
    # Inserta pocos cortes y NUNCA limpia con merge justo después
    inserted = 0
    for idx in [0, 10, 20, 30, 40, 50]:
        r = await send(ws, "select.edge_ring_from_edge", {"object":"Ship","edge_index":idx}, f"probe ring {idx}")
        if r.get("status") == "ok" and int(r.get("count", 0)) >= 8:
            sid = sid_of(r)
            rr = await send(ws, "mesh.loop_insert", {"object":"Ship","selection_id":sid,"cuts":1,"smooth":0.0})
            if rr.get("status") == "ok":
                inserted += 1
        if inserted >= 3:
            break

    # Un loop longitudinal (si existe)
    for idx in [5, 15, 25, 35]:
        r = await send(ws, "select.edge_loop_from_edge", {"object":"Ship","edge_index":idx}, f"probe loop {idx}")
        if r.get("status") == "ok" and int(r.get("count", 0)) >= 8:
            sid = sid_of(r)
            await send(ws, "mesh.loop_insert", {"object":"Ship","selection_id":sid,"cuts":1,"smooth":0.0})
            break

    # Validación y normales (sin merges peligrosos aquí)
    await send(ws, "mesh.validate", {"object":"Ship","check_self_intersections": False})
    await send(ws, "mesh.normals_recalc", {"object":"Ship","ensure_outside": True})
    await send(ws, "mesh.stats", {"object":"Ship"})





async def p_measure_iou(ws):
    print("\n" + "="*80); print(f"MEDIR IoU COMBO3 [{ts()}]"); print("="*80)
    if have(IMAGE_TOP) and have(IMAGE_LEFT) and have(IMAGE_FRONT):
        await send(ws, "similarity.iou_combo3", {
            "object":"Ship",
            "image_top": IMAGE_TOP,
            "image_side": IMAGE_LEFT,
            "image_front": IMAGE_FRONT,
            "alpha": 0.4, "beta": 0.3, "gamma": 0.3,
            "res": 512, "margin": 0.05, "threshold": 0.5
        })
    else:
        print("** Faltan rutas para IoU combo3, saltando.")

async def p_export(ws):
    print("\n" + "="*80); print(f"EXPORT FBX [{ts()}]"); print("="*80)
    await send(ws, "export_fbx", {"path": EXPORT_PATH})

# --------------------------- MAIN -------------------------------------------

STEPS = {
    "identify": p_identify,
    "clear": p_clear,
    "create_base": p_create_base,
    "densify_coarse": p_densify_coarse,         # <-- NUEVO
    "snap_top": p_snap_top,
    "snap_front": p_snap_front,
    "snap_side": p_snap_side,
    "densify_targeted": p_densify_targeted,     # <-- NUEVO
    "refine_bevel": p_refine_and_bevel,
    "iou": p_measure_iou,
    "export": p_export,
}

ORDER = [
    "identify",
    "clear",
    "create_base",
    "densify_coarse",     # subdivisión global
    "snap_top",
    "snap_front",
    # "snap_side",
    # "densify_targeted",   # loop-cuts controlados
    # "refine_bevel",       # bevel con validación/fallback (como te pasé)
    # "iou",
    # "export",
]

async def main(only=None, skip=None):
    run_list = list(ORDER)
    if only:
        sel = [s.strip() for s in only.split(",") if s.strip() in STEPS]
        run_list = sel
    if skip:
        sk = [s.strip() for s in skip.split(",")]
        run_list = [x for x in run_list if x not in sk]

    print("Conectando a", URI)
    async with websockets.connect(URI, ping_interval=20, ping_timeout=20) as ws:
        for name in run_list:
            fn = STEPS[name]
            try:
                await fn(ws)
            except Exception as e:
                print(f"!! Error en paso '{name}': {e}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Agente IA: modelado nave desde 3 plantillas")
    ap.add_argument("--only", help="Ejecutar solo estos pasos (coma-separados).")
    ap.add_argument("--skip", help="Omitir estos pasos (coma-separados).")
    args = ap.parse_args()
    asyncio.run(main(only=args.only, skip=args.skip))
