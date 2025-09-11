# ws_blender_full_test.py
# Pruebas modulares del servidor WebSocket de Blender 2.79
# Cliente probado con websockets 10/11 (el servidor usa websockets 7.0)

import asyncio
import json
import os
import argparse
from datetime import datetime

import websockets  # cliente

URI = "ws://127.0.0.1:8002"

# --- Plantillas de silueta (ajústalas a tus rutas) -------------------------
IMAGE_TOP   = r"D:\refs\generic_top.png"
IMAGE_SIDE  = r"D:\refs\generic_side.png"
IMAGE_FRONT = r"D:\refs\generic_front.png"

# --- Export de prueba ------------------------------------------------------
EXPORT_PATH = r"D:\ai-gamedev-pipeline\unity_project\Assets\Generated\test_ws_full.fbx"

# --- Helpers de consola ----------------------------------------------------
async def header(title: str):
    print("\n" + "="*80)
    print(f"{title}  [{datetime.now().strftime('%H:%M:%S')}]")
    print("="*80)

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

def img_ok(p: str) -> bool:
    return bool(p and os.path.isabs(p) and os.path.exists(p))

def safe_sid(resp: dict) -> int:
    try:
        return int(resp.get("selection_id", 0))
    except Exception:
        return 0

# --- Código Python remoto para utilidades que no existen como tools --------
EXEC_CLEAR = """import bpy
for obj in list(bpy.data.objects):
    try:
        bpy.data.objects.remove(obj, do_unlink=True)
    except:
        pass
"""

EXEC_DUPLICATE_FMT = """import bpy
name = "{name}"
new_name = "{new}"
ob = bpy.data.objects.get(name)
if ob is None:
    print("NO_OBJ")
else:
    cp = ob.copy()
    cp.data = ob.data.copy()
    cp.name = new_name
    bpy.context.scene.objects.link(cp)
    print("OK")
"""

EXEC_FIND_TWO_BORDER_LOOPS_FMT = """import bpy, bmesh, json
name = "{name}"
obj = bpy.data.objects.get(name)
if obj is None:
    print("null"); 
else:
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table(); bm.faces.ensure_lookup_table()
    border = [e for e in bm.edges if len(e.link_faces)==1]
    adj = {}
    for e in border:
        for v in e.verts:
            adj.setdefault(v.index, []).append(e.index)
    # camina loops por borde
    visited = set()
    loops = []
    for e in border:
        if e.index in visited: 
            continue
        # comienza por arista de borde y extiende por vértices frontera
        cur = [e.index]
        visited.add(e.index)
        grow = True
        while grow:
            grow = False
            last_edge_idx = cur[-1]
            # busca arista vecina que comparta un vértice
            last = bm.edges[last_edge_idx]
            vs = [v.index for v in last.verts]
            nxt = None
            for v_idx in vs:
                for e_idx in adj.get(v_idx, []):
                    if e_idx not in visited:
                        nxt = e_idx; break
                if nxt is not None: break
            if nxt is not None:
                cur.append(nxt); visited.add(nxt); grow = True
        loops.append(cur)
    loops_sorted = sorted(loops, key=lambda L: -len(L))
    out = loops_sorted[:2]
    print(json.dumps(out))
"""

EXEC_EDGE_COUNT_FMT = """import bpy
ob = bpy.data.objects.get("{name}")
print(len(ob.data.edges) if ob else -1)
"""

EXEC_VERT_COUNT_FMT = """import bpy
ob = bpy.data.objects.get("{name}")
print(len(ob.data.vertices) if ob else -1)
"""

# --- BLOQUES DE PRUEBAS ----------------------------------------------------

async def t_identify(ws):
    await header("IDENTIFY")
    await send_cmd(ws, "identify")

async def t_clear_scene(ws):
    await header("EXECUTE_PYTHON - limpiar escena")
    await send_cmd(ws, "execute_python", {"code": EXEC_CLEAR}, "execute_python(clear)")

async def t_create_bases(ws):
    await header("CREAR BASES Ship + Nose (outline)")
    await send_cmd(ws, "geom.create_base", {
        "name": "Ship",
        "outline": [
            [0.00,  1.00],[0.22,0.60],[0.38,0.35],[0.46,0.05],
            [0.40,-0.25],[0.24,-0.55],[0.10,-0.80],[0.00,-0.90]
        ],
        "thickness": 0.22, "mirror_x": True
    })
    await send_cmd(ws, "geom.create_base", {
        "name": "Nose",
        "outline": [[0.00,1.05],[0.10,0.95],[0.12,0.85],[0.08,0.75],[0.00,0.70]],
        "thickness": 0.18, "mirror_x": True
    })
    await send_cmd(ws, "mesh.stats", {"object": "Ship"})
    await send_cmd(ws, "mesh.stats", {"object": "Nose"})

async def t_basic_shaping(ws):
    await header("SHAPING: selección + extrusión (nariz), grow + sculpt, pods, cola")
    sel = await send_cmd(ws, "select.faces_by_range", {"object":"Ship","conds":[{"axis":"y","min":0.85}]})
    sid = safe_sid(sel)
    await send_cmd(ws, "edit.extrude_selection", {"object":"Ship","selection_id":sid,"translate":[0,0.18,0],"scale_about_center":[0.7,1,1]}, "extrude(nose)")
    sg = await send_cmd(ws, "select.grow", {"object":"Ship","selection_id":sid,"steps":1})
    sidg = safe_sid(sg)
    await send_cmd(ws, "edit.sculpt_selection", {"object":"Ship","selection_id":sidg,"move":[{"axis":"z","fn":"gauss","center_y":0.40,"width":0.28,"amplitude":0.12}]}, "sculpt(gauss)")
    selp = await send_cmd(ws, "select.faces_by_range", {"object":"Ship","conds":[{"axis":"y","min":0.15,"max":0.65},{"axis":"x","min":0.30}]})
    sidp = safe_sid(selp)
    await send_cmd(ws, "edit.extrude_selection", {"object":"Ship","selection_id":sidp,"translate":[0.18,0,0],"scale_about_center":[1,1,0.9]}, "extrude(pods)")
    selt = await send_cmd(ws, "select.faces_by_range", {"object":"Ship","conds":[{"axis":"y","max":-0.80}]})
    sidt = safe_sid(selt)
    await send_cmd(ws, "edit.extrude_selection", {"object":"Ship","selection_id":sidt,"translate":[0,-0.16,0],"inset":0.02}, "extrude(tail)")

async def t_cleanup_mirror_validate(ws):
    await header("CLEANUP + MIRROR + VALIDATE")
    await send_cmd(ws, "geom.cleanup", {"object":"Ship","merge_dist":0.0008,"recalc":True})
    await send_cmd(ws, "geom.mirror_x", {"object":"Ship","merge_dist":0.0008})
    await send_cmd(ws, "mesh.stats", {"object":"Ship"})
    await send_cmd(ws, "mesh.validate", {"object":"Ship","check_self_intersections":False})
    await send_cmd(ws, "mesh.normals_recalc", {"object":"Ship","ensure_outside":True})

async def t_curvature_move(ws):
    await header("CURVATURA: seleccionar vértices marcados y mover ligeramente")
    sel = await send_cmd(ws, "select.verts_by_curvature", {"object":"Ship","min_curv":0.10})
    sid = safe_sid(sel)
    await send_cmd(ws, "edit.move_verts", {"object":"Ship","selection_id":sid,"translate":[0,0,0.02]})

async def t_snapshot_restore(ws):
    await header("SNAPSHOT / RESTORE sobre Ship")
    snap = await send_cmd(ws, "mesh.snapshot", {"object":"Ship"})
    sid = snap.get("snapshot_id", 0)
    mid = await send_cmd(ws, "select.faces_in_bbox", {"object":"Ship","min":[-0.3,-0.1,-0.1],"max":[0.3,0.4,0.1]})
    sidm = safe_sid(mid)
    await send_cmd(ws, "edit.move_verts", {"object":"Ship","selection_id":sidm,"translate":[0,0,0.05],"scale_about_center":[1.05,1.0,1.05]}, "move(mid bump)")
    await send_cmd(ws, "mesh.restore", {"snapshot_id": sid, "object": "Ship"})

async def t_similarity_2views(ws):
    await header("SIMILARIDAD IoU TOP / SIDE / COMBO (si hay imágenes)")
    if img_ok(IMAGE_TOP):
        await send_cmd(ws, "similarity.iou_top", {"object":"Ship","image_path":IMAGE_TOP,"res":256,"margin":0.05,"threshold":0.5})
    else:
        print("** Saltando IoU TOP (ruta no válida)")
    if img_ok(IMAGE_SIDE):
        await send_cmd(ws, "similarity.iou_side", {"object":"Ship","image_path":IMAGE_SIDE,"res":256,"margin":0.05,"threshold":0.5})
    else:
        print("** Saltando IoU SIDE (ruta no válida)")
    if img_ok(IMAGE_TOP) and img_ok(IMAGE_SIDE):
        await send_cmd(ws, "similarity.iou_combo", {"object":"Ship","image_top":IMAGE_TOP,"image_side":IMAGE_SIDE,"alpha":0.6})

async def t_similarity_3views(ws):
    await header("SIMILARIDAD IoU FRONT + COMBO3 (si hay imágenes)")
    if img_ok(IMAGE_FRONT):
        await send_cmd(ws, "similarity.iou_front", {"object":"Ship","image_path":IMAGE_FRONT,"res":256,"margin":0.05,"threshold":0.5})
    else:
        print("** Saltando IoU FRONT (ruta no válida)")
    if img_ok(IMAGE_TOP) and img_ok(IMAGE_SIDE) and img_ok(IMAGE_FRONT):
        await send_cmd(ws, "similarity.iou_combo3", {
            "object":"Ship",
            "image_top":IMAGE_TOP, "image_side":IMAGE_SIDE, "image_front":IMAGE_FRONT,
            "alpha":0.34,"beta":0.33,"gamma":0.33
        })
    else:
        print("** Saltando IoU COMBO3 (faltan rutas)")

async def _pick_edge_index(ws, obj_name: str, candidates=None) -> int:
    # Estrategia simple: probar índices comunes hasta encontrar una selección válida
    if candidates is None:
        candidates = [0, 5, 10, 15, 20, 25, 30, 40, 50, 60]
    for i in candidates:
        r = await send_cmd(ws, "select.edge_loop_from_edge", {"object":obj_name,"edge_index":i}, f"probe loop edge={i}")
        if r.get("status") == "ok" and int(r.get("count", 0)) > 0:
            return i
    return -1

async def _edge_and_vert_counts(ws, obj_name: str):
    code_e = EXEC_EDGE_COUNT_FMT.format(name=obj_name)
    code_v = EXEC_VERT_COUNT_FMT.format(name=obj_name)
    r1 = await send_cmd(ws, "execute_python", {"code": code_e}, "edge_count(py)")
    r2 = await send_cmd(ws, "execute_python", {"code": code_v}, "vert_count(py)")
    def parse_int(resp): 
        try:
            return int((resp.get("stdout") or "").strip().splitlines()[-1])
        except Exception:
            return -1
    return parse_int(r1), parse_int(r2)

async def t_edges_loops_rings(ws):
    await header("SELECCIÓN por aristas: LOOP & RING + LOOP CUT + BEVEL")
    edge_idx = await _pick_edge_index(ws, "Ship")
    if edge_idx < 0:
        print("** No se encontró edge válido para loop/ring; intentando con edge 0 igualmente.")
        edge_idx = 0
    # Loop & Ring
    rloop = await send_cmd(ws, "select.edge_loop_from_edge", {"object":"Ship","edge_index":edge_idx})
    sid_loop = safe_sid(rloop)
    await send_cmd(ws, "select.edge_ring_from_edge", {"object":"Ship","edge_index":edge_idx})
    # Loop cut (sobre loop recogido)
    await send_cmd(ws, "mesh.loop_insert", {"object":"Ship","selection_id":sid_loop,"cuts":2,"smooth":0.0})
    # Bevel sobre ese loop
    await send_cmd(ws, "mesh.bevel", {"object":"Ship","selection_id":sid_loop,"offset":0.01,"segments":2,"profile":0.7,"clamp":True})

async def t_geodesic_and_snap(ws):
    await header("GEODESIC SELECT + SNAP a silueta (si hay imagen TOP)")
    # Semilla: intentamos vert 0; si no, 10…
    for seed in [0, 10, 20, 30]:
        selg = await send_cmd(ws, "select.geodesic", {"object":"Ship","seed_vert":seed,"radius":0.3})
        if selg.get("status") == "ok" and int(selg.get("count", 0)) > 0:
            sid = safe_sid(selg)
            if img_ok(IMAGE_TOP):
                await send_cmd(ws, "edit.snap_to_silhouette", {
                    "object":"Ship","selection_id":sid,"plane":"XY","image_path":IMAGE_TOP,
                    "strength":0.6,"iterations":8,"step":1.0,"res":256,"margin":0.05,"threshold":0.5
                })
            else:
                print("** Saltando SNAP (ruta TOP no válida)")
            break
    else:
        print("** No se pudo crear selección geodésica válida")

async def t_landmarks(ws):
    await header("LANDMARKS 2D→3D (plano YZ)")
    points = [
        {"uv":[0.62,0.38],"radius":0.12,"strength":0.9},
        {"uv":[0.35,0.70],"radius":0.10,"strength":0.6}
    ]
    await send_cmd(ws, "constraint.landmarks_apply", {"object":"Ship","plane":"YZ","points":points})

async def t_symmetries(ws):
    await header("SIMETRÍAS: mirror plano arbitrario y radial n-fold (sobre copia Ship_Sym)")
    # Duplicar Ship → Ship_Sym (para no tocar el original)
    code = EXEC_DUPLICATE_FMT.format(name="Ship", new="Ship_Sym")
    await send_cmd(ws, "execute_python", {"code": code}, "duplicate(Ship→Ship_Sym)")
    await send_cmd(ws, "geom.mirror_plane", {"object":"Ship_Sym","plane_point":[0,0,0],"plane_normal":[0.3,0.7,0.6],"merge_dist":0.0008})
    await send_cmd(ws, "geom.symmetry_radial", {"object":"Ship_Sym","axis":"Z","count":6,"merge_dist":0.0008})
    await send_cmd(ws, "mesh.stats", {"object":"Ship_Sym"})

async def t_topology(ws):
    await header("TOPOLOGÍA & REPARACIÓN: triangulate_beautify / fill_holes / (bridge_loops si hay loops frontera)")
    await send_cmd(ws, "mesh.triangulate_beautify", {"object":"Ship"})
    await send_cmd(ws, "mesh.fill_holes", {"object":"Ship"})
    # Intento de bridge_loops: buscamos 2 loops de borde vía execute_python
    code = EXEC_FIND_TWO_BORDER_LOOPS_FMT.format(name="Ship")
    r = await send_cmd(ws, "execute_python", {"code": code}, "find two border loops (py)")
    loops = None
    try:
        out = (r.get("stdout") or "").strip().splitlines()[-1]
        loops = json.loads(out) if out and out != "null" else None
    except Exception:
        loops = None
    if loops and isinstance(loops, list) and len(loops) >= 2 and all(isinstance(L, list) and L for L in loops[:2]):
        await send_cmd(ws, "mesh.bridge_loops", {"object":"Ship","loops":[loops[0], loops[1]]})
    else:
        print("** Saltando bridge_loops (no se detectaron dos loops de borde adecuados)")

async def t_merge_and_export(ws):
    await header("MERGE / STITCH (Ship + Nose) + VALIDATE + EXPORT FBX")
    await send_cmd(ws, "merge.stitch", {
        "object_a":"Ship","object_b":"Nose","out_name":"Ship_Merged",
        "delete":"B_inside_A","weld_dist":0.0008
    })
    await send_cmd(ws, "mesh.validate", {"object":"Ship_Merged","check_self_intersections":False})
    await send_cmd(ws, "mesh.normals_recalc", {"object":"Ship_Merged","ensure_outside":True})
    await send_cmd(ws, "mesh.stats", {"object":"Ship_Merged"})
    await send_cmd(ws, "export_fbx", {"path": EXPORT_PATH})

async def t_error_probe(ws):
    await header("ERROR PROBE: comprobar respuesta de error del servidor")
    # Forzamos un error: objeto inexistente y edge_index inválido
    resp = await send_cmd(
        ws,
        "select.edge_loop_from_edge",
        {"object": "__NO_SUCH_OBJECT__", "edge_index": -1},
        "error-probe edge_loop"
    )
    # Mensaje claro en consola según el resultado
    if resp.get("status") == "ok":
        print("!! Esperaba 'status:error' pero obtuve OK:", json.dumps(resp, ensure_ascii=False))
    else:
        print("✔ Error recibido como se esperaba:", json.dumps(resp, ensure_ascii=False))

# --- Orquestador -----------------------------------------------------------

TESTS = {
    "error_probe": t_error_probe, 
    "identify": t_identify,
    "clear": t_clear_scene,
    "create_bases": t_create_bases,
    "basic_shaping": t_basic_shaping,
    "cleanup_mirror_validate": t_cleanup_mirror_validate,
    "curvature_move": t_curvature_move,
    "snapshot_restore": t_snapshot_restore,
    "similarity_2views": t_similarity_2views,
    "similarity_3views": t_similarity_3views,
    "edges_loops_rings": t_edges_loops_rings,
    "geodesic_and_snap": t_geodesic_and_snap,
    "landmarks": t_landmarks,
    "symmetries": t_symmetries,
    "topology": t_topology,
    "merge_and_export": t_merge_and_export,
}

DEFAULT_ORDER = [
    "error_probe",
    "identify",
    "clear",
    "create_bases",
    "basic_shaping",
    "cleanup_mirror_validate",
    "curvature_move",
    "snapshot_restore",
    "similarity_2views",
    "similarity_3views",
    "edges_loops_rings",
    "geodesic_and_snap",
    "landmarks",
    "symmetries",
    "topology",
    "merge_and_export",
]

async def main(only=None, skip=None):
    print("Conectando a", URI)
    async with websockets.connect(URI, ping_interval=20, ping_timeout=20) as ws:
        run_list = list(DEFAULT_ORDER)
        if only:
            names = [x.strip() for x in only.split(",") if x.strip()]
            run_list = [n for n in names if n in TESTS]
        if skip:
            names = [x.strip() for x in skip.split(",") if x.strip()]
            run_list = [n for n in run_list if n not in names]

        for name in run_list:
            fn = TESTS[name]
            try:
                await fn(ws)
            except Exception as e:
                print(f"!! Error ejecutando '{name}': {e}")

        await asyncio.sleep(0.5)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Pruebas modulares WebSocket Blender")
    ap.add_argument("--only", help="Nombres de tests a ejecutar (coma-separados)", default=None)
    ap.add_argument("--skip", help="Nombres de tests a omitir (coma-separados)", default=None)
    args = ap.parse_args()
    asyncio.run(main(only=args.only, skip=args.skip))
