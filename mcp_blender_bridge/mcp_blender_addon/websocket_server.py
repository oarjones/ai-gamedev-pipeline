# Blender 2.79 – WebSocket server + API de modelado (bmesh-only)
# Requiere websockets==7.0 (Python 3.5)
#
# Comandos soportados (JSON):
#  - identify
#  - execute_python / execute_python_file
#  - export_fbx
#  - geom.create_base
#  - select.faces_by_range / select.faces_in_bbox / select.faces_by_normal / select.grow / select.verts_by_curvature
#  - edit.extrude_selection / edit.move_verts / edit.sculpt_selection
#  - geom.mirror_x / geom.cleanup
#  - mesh.stats / mesh.validate / mesh.normals_recalc
#  - mesh.snapshot / mesh.restore
#  - similarity.iou_top / similarity.iou_side / similarity.iou_combo
#  - merge.stitch
#
# Todas las tools de modelado usan bmesh + API de datos (sin cambiar de modo ni usar bpy.ops de edición).

from __future__ import print_function

import asyncio
import threading
import json
import os
import io
import traceback
import math

# --- Blender deps ---
try:
    import bpy
    import bmesh
    from mathutils import Vector, Matrix
except Exception:
    bpy = None

# --- WebSockets ---
try:
    import websockets
    from websockets.exceptions import ConnectionClosed
except Exception as ex:
    print("No se pudo importar 'websockets': {0}".format(ex))
    websockets = None

# --- Rutas base (ajusta si lo necesitas) ---
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
GENERATED_DIR = os.path.join(BASE_DIR, "unity_project", "Assets", "Generated")

# --- Estado del servidor ---
server_thread = None
loop = None
server = None


# --- Main-thread task queue (2.79-safe) ---
import threading, collections, time, logging

_TASKS = collections.deque()
_TASKS_LOCK = threading.Lock()

class _Task(object):
    def __init__(self, cmd, params):
        self.cmd = cmd
        self.params = params
        self.event = threading.Event()
        self.result = None

# Simple logging to a rotating file (optional)
try:
    import os as _os
    LOG_FILE = _os.path.join(_os.path.expanduser("~"), "mcp_blender_addon.log")
    logging.basicConfig(filename=LOG_FILE, level=logging.DEBUG, format="[%(asctime)s] %(levelname)s %(message)s")
except Exception:
    pass


# === Main-thread dispatcher built from the original handler's command-switch ===
def _run_command_mainthread(cmd, p):
    """Runs a command on the main thread. Returns the ACK dict."""
    # === API de modelado ===
    if cmd == "geom.create_base":
        ack = cmd_geom_create_base(
            name=p.get("name", "Mesh"),
            outline=p.get("outline", []),
            thickness=float(p.get("thickness", 0.2)),
            mirror_x=bool(p.get("mirror_x", False))
        )
    elif cmd == "select.faces_by_range":
        ack = cmd_select_faces_by_range(
            object_name=p.get("object", ""),
            conds=p.get("conds", [])
        )
    elif cmd == "select.faces_in_bbox":
        ack = cmd_select_faces_in_bbox(
            object_name=p.get("object", ""),
            bbox_min=p.get("min", [-1e9, -1e9, -1e9]),
            bbox_max=p.get("max", [1e9, 1e9, 1e9])
        )
    elif cmd == "select.faces_by_normal":
        ack = cmd_select_faces_by_normal(
            object_name=p.get("object", ""),
            axis=tuple(p.get("axis", (0, 0, 1))),
            min_dot=float(p.get("min_dot", 0.5)),
            max_dot=float(p.get("max_dot", 1.0))
        )
    elif cmd == "select.grow":
        ack = cmd_select_grow(
            object_name=p.get("object", ""),
            selection_id=int(p.get("selection_id", 0)),
            steps=int(p.get("steps", 1))
        )
    elif cmd == "select.verts_by_curvature":
        ack = cmd_select_verts_by_curvature(
            object_name=p.get("object", ""),
            min_curv=float(p.get("min_curv", 0.08)),
            in_bbox=p.get("in_bbox", None)
        )
    elif cmd == "edit.extrude_selection":
        ack = cmd_edit_extrude_selection(
            object_name=p.get("object", ""),
            selection_id=int(p.get("selection_id", 0)),
            translate=tuple(p.get("translate", (0, 0, 0))),
            scale_about_center=tuple(p.get("scale_about_center", (1, 1, 1))),
            inset=float(p.get("inset", 0.0))
        )
    elif cmd == "edit.move_verts":
        ack = cmd_edit_move_verts(
            object_name=p.get("object", ""),
            selection_id=int(p.get("selection_id", 0)),
            translate=tuple(p.get("translate", (0, 0, 0))),
            scale_about_center=tuple(p.get("scale_about_center", (1, 1, 1)))
        )
    elif cmd == "edit.sculpt_selection":
        ack = cmd_edit_sculpt_selection(
            object_name=p.get("object", ""),
            selection_id=int(p.get("selection_id", 0)),
            moves=p.get("move", [])
        )
    elif cmd == "geom.mirror_x":
        ack = cmd_geom_mirror_x(
            object_name=p.get("object", ""),
            merge_dist=float(p.get("merge_dist", 0.0008))
        )
    elif cmd == "geom.cleanup":
        ack = cmd_geom_cleanup(
            object_name=p.get("object", ""),
            merge_dist=float(p.get("merge_dist", 0.0008)),
            recalc=bool(p.get("recalc", True))
        )
    elif cmd == "mesh.stats":
        ack = cmd_mesh_stats(object_name=p.get("object", ""))
    elif cmd == "mesh.validate":
        ack = cmd_mesh_validate(
            object_name=p.get("object", ""),
            check_self_intersections=bool(p.get("check_self_intersections", False))
        )
    elif cmd == "mesh.snapshot":
        ack = cmd_mesh_snapshot(object_name=p.get("object", ""))
    elif cmd == "mesh.restore":
        ack = cmd_mesh_restore(
            snapshot_id=int(p.get("snapshot_id", 0)),
            object_name=p.get("object", None)
        )
    elif cmd == "mesh.normals_recalc":
        ack = cmd_mesh_normals_recalc(
            object_name=p.get("object",""),
            ensure_outside=bool(p.get("ensure_outside",True))
        )
    elif cmd == "similarity.iou_top":
        ack = cmd_similarity_iou_top(
            object_name=p.get("object", ""),
            image_path=p.get("image_path", ""),
            res=int(p.get("res", 256)),
            margin=float(p.get("margin", 0.05)),
            threshold=float(p.get("threshold", 0.5))
        )
    elif cmd == "similarity.iou_side":
        ack = cmd_similarity_iou_side(
            object_name=p.get("object",""),
            image_path=p.get("image_path",""),
            res=int(p.get("res",256)),
            margin=float(p.get("margin",0.05)),
            threshold=float(p.get("threshold",0.5))
        )
    elif cmd == "similarity.iou_combo":
        ack = cmd_similarity_iou_combo(
            object_name=p.get("object",""),
            image_top=p.get("image_top",""),
            image_side=p.get("image_side",""),
            res=int(p.get("res",256)),
            margin=float(p.get("margin",0.05)),
            threshold=float(p.get("threshold",0.5)),
            alpha=float(p.get("alpha",0.5))
        )
    elif cmd == "merge.stitch":
        ack = cmd_merge_stitch(
            object_a=p.get("object_a",""),
            object_b=p.get("object_b",""),
            out_name=p.get("out_name","Merged"),
            delete=p.get("delete","B_inside_A"),
            weld_dist=float(p.get("weld_dist",0.001)),
            res=int(p.get("res",256)),
            margin=float(p.get("margin",0.03))
        )

    # --- IoU FRONT + combo 3 vistas ---
    elif cmd == "similarity.iou_front":
        ack = cmd_similarity_iou_front(
            object_name=p.get("object",""),
            image_path=p.get("image_path",""),
            res=int(p.get("res",256)),
            margin=float(p.get("margin",0.05)),
            threshold=float(p.get("threshold",0.5))
        )
    elif cmd == "similarity.iou_combo3":
        ack = cmd_similarity_iou_combo3(
            object_name=p.get("object",""),
            image_top=p.get("image_top",""),
            image_side=p.get("image_side",""),
            image_front=p.get("image_front",""),
            res=int(p.get("res",256)),
            margin=float(p.get("margin",0.05)),
            threshold=float(p.get("threshold",0.5)),
            alpha=float(p.get("alpha",0.34)),
            beta=float(p.get("beta",0.33)),
            gamma=float(p.get("gamma",0.33))
        )

    # --- loops & rings ---
    elif cmd == "select.edge_loop_from_edge":
        ack = cmd_select_edge_loop_from_edge(
            object_name=p.get("object",""),
            edge_index=int(p.get("edge_index",0))
        )
    elif cmd == "select.edge_ring_from_edge":
        ack = cmd_select_edge_ring_from_edge(
            object_name=p.get("object",""),
            edge_index=int(p.get("edge_index",0))
        )

    # --- loop cut / subdivisión ---
    elif cmd == "mesh.loop_insert":
        ack = cmd_mesh_loop_insert(
            object_name=p.get("object",""),
            edges=p.get("edges",None),
            selection_id=p.get("selection_id",None),
            cuts=int(p.get("cuts",1)),
            smooth=float(p.get("smooth",0.0))
        )

    # --- bevel ---
    elif cmd == "mesh.bevel":
        ack = cmd_mesh_bevel(
            object_name=p.get("object",""),
            edges=p.get("edges",None),
            verts=p.get("verts",None),
            selection_id=p.get("selection_id",None),
            offset=float(p.get("offset",0.01)),
            segments=int(p.get("segments",2)),
            profile=float(p.get("profile",0.7)),
            clamp=bool(p.get("clamp",True)),
            auto_sharp_angle=p.get("auto_sharp_angle",None)
        )

    # --- geodesic select ---
    elif cmd == "select.geodesic":
        ack = cmd_select_geodesic(
            object_name=p.get("object",""),
            seed_vert=p.get("seed_vert",None),
            selection_id=p.get("selection_id",None),
            radius=float(p.get("radius",0.25))
        )

    # --- snap a silueta ---
    elif cmd == "edit.snap_to_silhouette":
        ack = cmd_edit_snap_to_silhouette(
            object_name=p.get("object",""),
            selection_id=int(p.get("selection_id",0)),
            plane=p.get("plane","XY"),
            image_path=p.get("image_path",""),
            strength=float(p.get("strength",0.5)),
            iterations=int(p.get("iterations",8)),
            step=float(p.get("step",1.0)),
            res=int(p.get("res",256)),
            margin=float(p.get("margin",0.05)),
            threshold=float(p.get("threshold",0.5))
        )

    # --- landmarks 2D->3D ---
    elif cmd == "constraint.landmarks_apply":
        ack = cmd_constraint_landmarks_apply(
            object_name=p.get("object",""),
            plane=p.get("plane","XY"),
            points=p.get("points",[])
        )

    # --- simetrías avanzadas ---
    elif cmd == "geom.mirror_plane":
        ack = cmd_geom_mirror_plane(
            object_name=p.get("object",""),
            plane_point=tuple(p.get("plane_point",(0,0,0))),
            plane_normal=tuple(p.get("plane_normal",(1,0,0))),
            merge_dist=float(p.get("merge_dist",0.0008))
        )
    elif cmd == "geom.symmetry_radial":
        ack = cmd_geom_symmetry_radial(
            object_name=p.get("object",""),
            axis=p.get("axis","Z"),
            count=int(p.get("count",6)),
            merge_dist=float(p.get("merge_dist",0.0008))
        )

    # --- topología & reparación ---
    elif cmd == "mesh.triangulate_beautify":
        ack = cmd_mesh_triangulate_beautify(object_name=p.get("object",""))
    elif cmd == "mesh.join_quads":
        ack = cmd_mesh_join_quads(
            object_name=p.get("object",""),
            angle_face=float(p.get("angle_face",0.1)),
            angle_shape=float(p.get("angle_shape",0.5))
        )
    elif cmd == "mesh.bridge_loops":
        ack = cmd_mesh_bridge_loops(
            object_name=p.get("object",""),
            loops=p.get("loops",[])
        )
    elif cmd == "mesh.fill_holes":
        ack = cmd_mesh_fill_holes(object_name=p.get("object",""))


    # === comandos utilitarios existentes ===
    elif cmd == "export_fbx":
        try:
            ack = {"status": "ok", "path": export_fbx(**p)}
        except Exception as e:
            ack = {"status":"error","message":"{}: {}".format(e.__class__.__name__, e),
                   "trace": traceback.format_exc()}
    elif cmd == "execute_python":
        stdout, stderr, err = execute_python(p.get("code", ""))
        ack = {"status": "ok" if err is None else "error", "stdout": stdout, "stderr": stderr}
        if err is not None:
            ack["message"] = err
    elif cmd == "execute_python_file":
        try:
            stdout, stderr, err = execute_python_file(p.get("path", ""))
            ack = {"status": "ok" if err is None else "error", "stdout": stdout, "stderr": stderr}
            if err is not None:
                ack["message"] = err
        except Exception as e:
            ack = {"status":"error","message":"{}: {}".format(e.__class__.__name__, e),
                   "trace": traceback.format_exc()}
    elif cmd == "identify":
        ack = {
            "status": "ok",
            "module_file": __file__,
            "websockets_version": getattr(websockets, "__version__", "unknown"),
            "blender_version": getattr(bpy.app, "version", None),
        }
    else:
        ack = {"status": "ok", "echo": {"command": cmd, "params": p}}

    return ack

# --- Modal operator that pumps the task queue on the main thread ---
import bpy

class MCP_OT_TaskPump(bpy.types.Operator):
    bl_idname = "wm.mcp_task_pump"
    bl_label = "MCP Task Pump"
    _timer = None

    def modal(self, context, event):
        if event.type == 'TIMER':
            while True:
                with _TASKS_LOCK:
                    if not _TASKS:
                        break
                    t = _TASKS.popleft()
                try:
                    res = _run_command_mainthread(t.cmd, t.params)
                except Exception as e:
                    import traceback as _tb
                    res = {"status": "error", "message": "%s: %s" % (e.__class__.__name__, e),
                           "trace": _tb.format_exc()}
                t.result = res
                t.event.set()
        return {'PASS_THROUGH'}

    def execute(self, context):
        wm = context.window_manager
        # 20ms timer; Blender 2.79 signature is event_timer_add(time_step, window)
        try:
            self._timer = wm.event_timer_add(0.02, context.window)
        except TypeError:
            # Fallback for possible API differences
            self._timer = wm.event_timer_add(0.02, window=context.window)
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}

# =====================================================================================
# Decorador para tools: captura excepciones y devuelve error estructurado (MCP-friendly)
# =====================================================================================
def _tool(fn):
    """Envuelve una tool: captura excepciones y devuelve un dict de error trazable para el MCP."""
    def _wrap(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            tb = traceback.format_exc()
            return {
                "status": "error",
                "tool": fn.__name__,
                "message": "{}: {}".format(e.__class__.__name__, e),
                "trace": tb
            }
    return _wrap

# =====================================================================================
# Utilidades generales
# =====================================================================================

def export_fbx(path):
    """Exporta la escena a FBX con ejes compatibles con Unity.
    Usa bpy.ops SOLO aquí, como paso final independiente.
    """
    if bpy is None:
        print("bpy no disponible: export_fbx es un stub")
        return path

    if isinstance(path, str):
        path = path.replace("/", os.sep).replace("\\", os.sep)
    else:
        path = "export.fbx"

    if os.path.isabs(path):
        full_path = path
    else:
        full_path = os.path.join(GENERATED_DIR, path)

    try:
        dirpath = os.path.dirname(full_path)
        if dirpath and not os.path.exists(dirpath):
            os.makedirs(dirpath)

        # Asentar depsgraph en 2.79 por seguridad
        try:
            bpy.context.scene.update()
        except Exception:
            pass
        try:
            bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
        except Exception:
            pass

        bpy.ops.export_scene.fbx(
            filepath=full_path,
            apply_unit_scale=True,
            bake_space_transform=False,
            axis_forward='-Z', axis_up='Y'
        )
        return full_path
    except Exception as exc:
        print("Error al exportar FBX: {0}".format(exc))
        raise

def execute_python(code):
    """Ejecuta código Python arbitrario y captura stdout/stderr + error estructurado."""
    local_env = {"bpy": bpy, "bmesh": bmesh, "Vector": Vector, "Matrix": Matrix, "math": math}
    stdout_io = io.StringIO()
    stderr_io = io.StringIO()
    err_msg = None
    try:
        from contextlib import redirect_stdout, redirect_stderr
        with redirect_stdout(stdout_io), redirect_stderr(stderr_io):
            exec(code, local_env, local_env)
    except Exception as exc:
        err_msg = "{}: {}".format(exc.__class__.__name__, exc)
        stderr_io.write("\n" + traceback.format_exc())
    return stdout_io.getvalue(), stderr_io.getvalue(), err_msg

def execute_python_file(path):
    """Lee un archivo .py y lo ejecuta (equivalente a execute_python pero desde disco)."""
    if not path:
        raise ValueError("Ruta del script no proporcionada")
    if not os.path.isabs(path):
        path = os.path.join(BASE_DIR, path)
    if not os.path.exists(path):
        raise FileNotFoundError("No existe: {0}".format(path))
    with open(path, "r", encoding="utf-8") as f:
        code = f.read()
    return execute_python(code)

# =====================================================================================
# API de modelado (bmesh-only) – helpers y estado
# =====================================================================================

# Almacén efímero de selecciones entre llamadas (IDs para caras/vértices)
_selection_store = {"next_id": 1, "selections": {}}

def _store_selection(obj_name, faces_idx=None, verts_idx=None, edges_idx=None):
    """Guarda una selección efímera (caras, vértices o aristas) y devuelve un selection_id."""
    sid = _selection_store["next_id"]
    _selection_store["next_id"] += 1
    _selection_store["selections"][sid] = {
        "obj": obj_name,
        "faces": faces_idx or [],
        "verts": verts_idx or [],
        "edges": edges_idx or []
    }
    return sid


def _fetch_selection(sid):
    """Recupera una selección efímera por ID."""
    return _selection_store["selections"].get(sid)

def _obj(name):
    """Devuelve el objeto por nombre, o None si no existe."""
    return bpy.data.objects.get(name)

def _bm_from_object(obj):
    """Crea un bmesh desde el mesh de un objeto (con tablas lookup listas)."""
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    return bm

def _bm_to_object(obj, bm, recalc_normals=True):
    """Escribe el bmesh de vuelta al objeto y actualiza el mesh."""
    me = obj.data
    if recalc_normals:
        bm.normal_update()
    bm.to_mesh(me)
    me.update()

def _remove_doubles(bm, dist=0.0008):
    """Fusiona vértices próximos (remove doubles) con la distancia especificada."""
    try:
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=dist)
    except Exception:
        pass

def _tri_count(obj):
    """Cuenta triángulos aproximando: tris=1, quads=2, n-gon = n-2.
    Libera el mesh temporal para evitar fugas.
    """
    m = obj.to_mesh(bpy.context.scene, True, 'PREVIEW')
    tris = sum(
        (1 if len(p.vertices) == 3 else
         2 if len(p.vertices) == 4 else
         max(0, len(p.vertices) - 2))
        for p in m.polygons
    )
    try:
        bpy.data.meshes.remove(m)
    except Exception:
        pass
    return tris

def _mesh_bbox(obj):
    """Devuelve el bounding box (min/max) del mesh en coordenadas locales."""
    vs = obj.data.vertices
    if not vs:
        return {"min": [0, 0, 0], "max": [0, 0, 0]}
    xs = [v.co.x for v in vs]
    ys = [v.co.y for v in vs]
    zs = [v.co.z for v in vs]
    return {"min": [min(xs), min(ys), min(zs)],
            "max": [max(xs), max(ys), max(zs)]}

# ---- Helper 2.79: matriz de escala anisotrópica (sustituto de Matrix.Diagonal) ----
def _scale_matrix(sx, sy, sz):
    """Devuelve una matriz 4x4 de escala anisotrópica válida en 2.79."""
    sx, sy, sz = float(sx), float(sy), float(sz)
    Sx = Matrix.Scale(sx, 4, Vector((1,0,0)))
    Sy = Matrix.Scale(sy, 4, Vector((0,1,0)))
    Sz = Matrix.Scale(sz, 4, Vector((0,0,1)))
    return Sx * Sy * Sz

# =====================================================================================
# Similitud IoU con silueta 2D (TOP y SIDE) + rasterizado auxiliar
# =====================================================================================

def _rasterize_mesh_xy(obj, res=256, margin=0.05):
    """Proyecta la malla en XY y rasteriza triángulos en una cuadrícula booleana res×res."""
    me = obj.data
    xs = [v.co.x for v in me.vertices]
    ys = [v.co.y for v in me.vertices]
    if not xs or not ys:
        return [[False] * res for _ in range(res)]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    w = maxx - minx
    h = maxy - miny
    pad = margin * max(w, h) + 1e-9
    minx -= pad
    maxx += pad
    miny -= pad
    maxy += pad
    sx = (res - 1) / (maxx - minx)
    sy = (res - 1) / (maxy - miny)

    def pl(pt):
        # mapea (x,y) a coordenadas de píxel
        return (int((pt.x - minx) * sx + 0.5), int((pt.y - miny) * sy + 0.5))

    mask = [[False] * res for _ in range(res)]
    for poly in me.polygons:
        idxs = list(poly.vertices)
        if len(idxs) < 3:
            continue
        v0 = me.vertices[idxs[0]].co
        for i in range(1, len(idxs) - 1):
            v1 = me.vertices[idxs[i]].co
            v2 = me.vertices[idxs[i + 1]].co
            x0, y0 = pl(v0)
            x1, y1 = pl(v1)
            x2, y2 = pl(v2)
            xmin = max(0, min(x0, x1, x2))
            xmax = min(res - 1, max(x0, x1, x2))
            ymin = max(0, min(y0, y1, y2))
            ymax = min(res - 1, max(y0, y1, y2))
            denom = float((y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2))
            if abs(denom) < 1e-9:
                continue
            for yy in range(ymin, ymax + 1):
                for xx in range(xmin, xmax + 1):
                    w0 = ((y1 - y2) * (xx - x2) + (x2 - x1) * (yy - y2)) / denom
                    w1 = ((y2 - y0) * (xx - x2) + (x0 - x2) * (yy - y2)) / denom
                    w2 = 1.0 - w0 - w1
                    if w0 >= 0 and w1 >= 0 and w2 >= 0:
                        mask[yy][xx] = True
    return mask

def _mesh_world_verts_faces(obj):
    """Devuelve (verts_world, faces_idx) del objeto."""
    me = obj.data
    M = obj.matrix_world
    verts = [(M * v.co.to_4d()).to_3d() for v in me.vertices]
    faces = [tuple(p.vertices) for p in me.polygons]
    return verts, faces

def _rasterize_verts_faces_plane(verts, faces, plane='XY', res=256, margin=0.05):
    """Rasteriza un mesh dado por (verts, faces) en el plano indicado ('XY' o 'XZ')."""
    if not verts:
        return [[False]*res for _ in range(res)], {'minx':0,'maxx':1,'miny':0,'maxy':1}

    if plane == 'XY':
        xs = [v.x for v in verts]; ys = [v.y for v in verts]
        pick = lambda idx: (verts[idx].x, verts[idx].y)
    elif plane == 'XZ':
        xs = [v.x for v in verts]; ys = [v.z for v in verts]
        pick = lambda idx: (verts[idx].x, verts[idx].z)
    else:
        raise ValueError("Plano no soportado: {0}".format(plane))

    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    w = maxx - minx; h = maxy - miny
    pad = margin * max(w, h) + 1e-9
    minx -= pad; maxx += pad; miny -= pad; maxy += pad
    sx = (res-1)/(maxx-minx); sy = (res-1)/(maxy-miny)

    def to_px(pt):
        x,y = pt
        return (int((x-minx)*sx+0.5), int((y-miny)*sy+0.5))

    mask = [[False]*res for _ in range(res)]
    for poly in faces:
        if len(poly) < 3: 
            continue
        v0 = pick(poly[0])
        x0,y0 = to_px(v0)
        for i in range(1, len(poly)-1):
            x1,y1 = to_px(pick(poly[i]))
            x2,y2 = to_px(pick(poly[i+1]))
            xmin = max(0, min(x0,x1,x2)); xmax = min(res-1, max(x0,x1,x2))
            ymin = max(0, min(y0,y1,y2)); ymax = min(res-1, max(y0,y1,y2))
            denom = float((y1 - y2)*(x0 - x2) + (x2 - x1)*(y0 - y2))
            if abs(denom) < 1e-9: 
                continue
            for yy in range(ymin, ymax+1):
                for xx in range(xmin, xmax+1):
                    w0 = ((y1 - y2)*(xx - x2) + (x2 - x1)*(yy - y2)) / denom
                    w1 = ((y2 - y0)*(xx - x2) + (x0 - x2)*(yy - y2)) / denom
                    w2 = 1.0 - w0 - w1
                    if w0 >= 0 and w1 >= 0 and w2 >= 0:
                        mask[yy][xx] = True
    bounds = {'minx':minx,'maxx':maxx,'miny':miny,'maxy':maxy}
    return mask, bounds

def _mask_sample(mask, bounds, x, y):
    """Consulta booleana de la máscara (x,y) en coords reales del plano utilizado en rasterización."""
    res_y = len(mask); res_x = len(mask[0]) if res_y else 0
    if res_x == 0 or res_y == 0:
        return False
    minx,maxx,miny,maxy = bounds['minx'],bounds['maxx'],bounds['miny'],bounds['maxy']
    if x < minx or x > maxx or y < miny or y > maxy:
        return False
    sx = (res_x-1)/(maxx-minx); sy = (res_y-1)/(maxy-miny)
    ix = int((x-minx)*sx + 0.5); iy = int((y-miny)*sy + 0.5)
    ix = max(0, min(res_x-1, ix)); iy = max(0, min(res_y-1, iy))
    return bool(mask[iy][ix])


# -------- Helpers de plano local (XY/XZ/YZ) --------
def _plane_axes(plane):
    plane = plane.upper()
    if plane == 'XY': return ('x','y')
    if plane == 'XZ': return ('x','z')
    if plane == 'YZ': return ('y','z')
    raise ValueError("Plano no soportado: {}".format(plane))

def _get_uv_from_vec(co, plane):
    a,b = _plane_axes(plane)
    return getattr(co, a), getattr(co, b)

def _set_uv_on_vec(co, plane, u, v):
    a,b = _plane_axes(plane)
    setattr(co, a, float(u))
    setattr(co, b, float(v))

def _bounds_on_plane_local(obj, plane):
    a,b = _plane_axes(plane)
    vs = obj.data.vertices
    if not vs:
        return {'minx':0,'maxx':1,'miny':0,'maxy':1}
    xs = [getattr(v.co, a) for v in vs]
    ys = [getattr(v.co, b) for v in vs]
    return {'minx':min(xs),'maxx':max(xs),'miny':min(ys),'maxy':max(ys)}

def _rasterize_mesh_plane_local(obj, plane='YZ', res=256, margin=0.05):
    """Rasteriza el OBJ en un plano local ('XY','XZ','YZ'), devolviendo (mask, bounds)."""
    b = _bounds_on_plane_local(obj, plane)
    minx,maxx,miny,maxy = b['minx'],b['maxx'],b['miny'],b['maxy']
    w = maxx-minx; h = maxy-miny
    pad = margin * max(w, h) + 1e-9
    minx -= pad; maxx += pad; miny -= pad; maxy += pad
    sx = (res-1)/(maxx-minx); sy = (res-1)/(maxy-miny)

    def to_px(u,v):
        return (int((u-minx)*sx+0.5), int((v-miny)*sy+0.5))

    mask = [[False]*res for _ in range(res)]
    me = obj.data
    a,bn = _plane_axes(plane)
    for poly in me.polygons:
        idxs = list(poly.vertices)
        if len(idxs) < 3: continue
        def pick(i):
            c = me.vertices[i].co
            return (getattr(c, a), getattr(c, bn))
        u0,v0 = pick(idxs[0]); x0,y0 = to_px(u0,v0)
        for i in range(1, len(idxs)-1):
            u1,v1 = pick(idxs[i]);   x1,y1 = to_px(u1,v1)
            u2,v2 = pick(idxs[i+1]); x2,y2 = to_px(u2,v2)
            xmin = max(0, min(x0,x1,x2)); xmax = min(res-1, max(x0,x1,x2))
            ymin = max(0, min(y0,y1,y2)); ymax = min(res-1, max(y0,y1,y2))
            denom = float((y1 - y2)*(x0 - x2) + (x2 - x1)*(y0 - y2))
            if abs(denom) < 1e-9: continue
            for yy in range(ymin, ymax+1):
                for xx in range(xmin, xmax+1):
                    w0 = ((y1 - y2)*(xx - x2) + (x2 - x1)*(yy - y2)) / denom
                    w1 = ((y2 - y0)*(xx - x2) + (x0 - x2)*(yy - y2)) / denom
                    w2 = 1.0 - w0 - w1
                    if w0 >= 0 and w1 >= 0 and w2 >= 0:
                        mask[yy][xx] = True
    bounds = {'minx':minx,'maxx':maxx,'miny':miny,'maxy':maxy}
    return mask, bounds

def _mask_val(mask, x, y):
    H = len(mask); W = len(mask[0]) if H else 0
    if W==0 or H==0: return 0.0
    x = max(0, min(W-1, x)); y = max(0, min(H-1, y))
    return 1.0 if mask[y][x] else 0.0

def _mask_grad(mask, x, y):
    """Gradiente simple (centrado) en píxeles: devuelve (gx, gy)."""
    gx = _mask_val(mask, x+1, y) - _mask_val(mask, x-1, y)
    gy = _mask_val(mask, x, y+1) - _mask_val(mask, x, y-1)
    return (gx*0.5, gy*0.5)




def _load_mask_image(path, res=256, threshold=0.5):
    """Carga una imagen y la convierte en máscara booleana (umbral por luminancia) reescalada a res×res."""
    try:
        img = bpy.data.images.load(path)
    except Exception as e:
        raise RuntimeError("No se pudo cargar la imagen de referencia: {0}".format(e))
    w, h = img.size
    px = list(img.pixels)  # RGBA floats

    def sample(u, v):
        x = int(max(0, min(w - 1, round(u * (w - 1)))))
        y = int(max(0, min(h - 1, round(v * (h - 1)))))
        i = (y * w + x) * 4
        r, g, b = px[i], px[i + 1], px[i + 2]
        lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
        return lum

    mask = [[False] * res for _ in range(res)]
    for j in range(res):
        v = j / float(res - 1)
        for i in range(res):
            u = i / float(res - 1)
            mask[j][i] = sample(u, v) >= float(threshold)
    try:
        bpy.data.images.remove(img)
    except Exception:
        pass
    return mask

def _iou(maskA, maskB):
    """Calcula Intersection over Union (IoU) entre dos máscaras booleanas del mismo tamaño."""
    inter = 0
    union = 0
    H = len(maskA)
    W = len(maskA[0]) if H else 0
    for y in range(H):
        for x in range(W):
            a = 1 if maskA[y][x] else 0
            b = 1 if maskB[y][x] else 0
            inter += 1 if (a and b) else 0
            union += 1 if (a or b) else 0
    return (float(inter) / float(union)) if union else 0.0

# =====================================================================================
# Comandos de modelado y análisis (con @ _tool)
# =====================================================================================

@_tool
def cmd_geom_create_base(name, outline, thickness=0.2, mirror_x=False):
    """Crea una base a partir de un contorno 2D (XY), extruye para dar grosor y (opcional) duplica espejado en X."""
    bm = bmesh.new()
    vs = []
    for p in outline:
        if len(p) >= 2:
            x, y = float(p[0]), float(p[1])
            vs.append(bm.verts.new((x, y, 0.0)))
    f = bm.faces.new(vs)
    res = bmesh.ops.extrude_face_region(bm, geom=[f])
    up_verts = [e for e in res["geom"] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=up_verts, vec=(0, 0, thickness))
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, -thickness / 2.0))

    if mirror_x:
        dup = bmesh.ops.duplicate(bm, geom=list(bm.verts) + list(bm.edges) + list(bm.faces))
        new_vs = [g for g in dup["geom"] if isinstance(g, bmesh.types.BMVert)]
        bmesh.ops.scale(bm, verts=new_vs, vec=(-1, 1, 1))
        _remove_doubles(bm, 0.0008)

    me = bpy.data.meshes.new(name + "Mesh")
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.objects.link(obj)
    _bm_to_object(obj, bm)
    bm.free()
    return {"status": "ok", "object": obj.name}

@_tool
def cmd_select_faces_by_range(object_name, conds):
    """Selecciona caras cuyo centro cumpla un conjunto de rangos por eje (x/y/z)."""
    obj = _obj(object_name)
    if obj is None:
        return {"status": "error", "message": "objeto no encontrado"}
    bm = _bm_from_object(obj)
    faces_idx = []
    for f in bm.faces:
        c = f.calc_center_bounds()
        ok = True
        for cond in (conds or []):
            ax = cond.get("axis", "y")
            mn = cond.get("min", -1e9)
            mx = cond.get("max", 1e9)
            v = getattr(c, ax)
            if v < mn or v > mx:
                ok = False
                break
        if ok:
            faces_idx.append(f.index)
    sid = _store_selection(obj.name, faces_idx=faces_idx)
    bm.free()
    return {"status": "ok", "selection_id": sid, "count": len(faces_idx)}

@_tool
def cmd_select_faces_in_bbox(object_name, bbox_min, bbox_max):
    """Selecciona caras cuyo centro esté dentro de una caja axis-aligned dada (min/max)."""
    obj = _obj(object_name)
    if obj is None:
        return {"status": "error", "message": "objeto no encontrado"}
    bm = _bm_from_object(obj)
    faces_idx = []
    xmin, ymin, zmin = bbox_min
    xmax, ymax, zmax = bbox_max
    for f in bm.faces:
        c = f.calc_center_bounds()
        if (xmin <= c.x <= xmax) and (ymin <= c.y <= ymax) and (zmin <= c.z <= zmax):
            faces_idx.append(f.index)
    sid = _store_selection(obj.name, faces_idx=faces_idx)
    bm.free()
    return {"status": "ok", "selection_id": sid, "count": len(faces_idx)}

@_tool
def cmd_select_faces_by_normal(object_name, axis=(0, 0, 1), min_dot=0.5, max_dot=1.0):
    """Selecciona caras según el ángulo de su normal con un eje dado (producto punto en [min_dot,max_dot])."""
    obj = _obj(object_name)
    if obj is None:
        return {"status": "error", "message": "objeto no encontrado"}
    bm = _bm_from_object(obj)
    ax = Vector(axis)
    try:
        ax.normalize()
    except Exception:
        pass
    faces_idx = []
    for f in bm.faces:
        n = f.normal.copy()
        try:
            n.normalize()
        except Exception:
            pass
        d = ax.dot(n)
        if d >= float(min_dot) and d <= float(max_dot):
            faces_idx.append(f.index)
    sid = _store_selection(obj.name, faces_idx=faces_idx)
    bm.free()
    return {"status": "ok", "selection_id": sid, "count": len(faces_idx)}

@_tool
def cmd_select_grow(object_name, selection_id, steps=1):
    """Expande (crece) una selección de caras N veces siguiendo la conectividad (anillos/bordes)."""
    sel = _fetch_selection(selection_id)
    if not sel or sel["obj"] != object_name:
        return {"status": "error", "message": "seleccion inválida"}
    obj = _obj(object_name)
    bm = _bm_from_object(obj)
    cur = set(bm.faces[i] for i in sel["faces"] if i < len(bm.faces))
    for _ in range(max(1, int(steps))):
        nxt = set(cur)
        for f in list(cur):
            for e in f.edges:
                for nf in e.link_faces:
                    nxt.add(nf)
        cur = nxt
    ids = [f.index for f in cur]
    sid = _store_selection(obj.name, faces_idx=ids)
    bm.free()
    return {"status": "ok", "selection_id": sid, "count": len(ids)}

def _vertex_curvature(bm, v):
    """Aproxima la curvatura en un vértice mediante el ángulo diédrico medio de sus aristas."""
    tot = 0.0
    cnt = 0
    for e in v.link_edges:
        fs = list(e.link_faces)
        if len(fs) == 2:
            n1 = fs[0].normal
            n2 = fs[1].normal
            d = max(-1.0, min(1.0, n1.dot(n2)))
            ang = 1.0 - d  # mayor valor = mayor "curvatura"
            tot += ang
            cnt += 1
    return (tot / cnt) if cnt else 0.0

@_tool
def cmd_select_verts_by_curvature(object_name, min_curv=0.08, in_bbox=None):
    """Selecciona vértices con curvatura estimada >= min_curv (opcionalmente limitada a una caja)."""
    obj = _obj(object_name)
    if obj is None:
        return {"status": "error", "message": "objeto no encontrado"}
    bm = _bm_from_object(obj)
    verts_idx = []
    use_bbox = bool(in_bbox)
    if use_bbox:
        (xmin, ymin, zmin), (xmax, ymax, zmax) = in_bbox
    for i, v in enumerate(bm.verts):
        if use_bbox:
            c = v.co
            if not (xmin <= c.x <= xmax and ymin <= c.y <= ymax and zmin <= c.z <= zmax):
                continue
        if _vertex_curvature(bm, v) >= float(min_curv):
            verts_idx.append(i)
    sid = _store_selection(obj.name, verts_idx=verts_idx)
    bm.free()
    return {"status": "ok", "selection_id": sid, "count": len(verts_idx)}

@_tool
def cmd_edit_extrude_selection(object_name, selection_id, translate=(0, 0, 0), scale_about_center=(1, 1, 1), inset=0.0):
    """Extruye la selección de caras; mueve y escala los nuevos vértices respecto a su centro; opcional inset."""
    sel = _fetch_selection(selection_id)
    if not sel or sel["obj"] != object_name:
        return {"status": "error", "message": "seleccion inválida"}
    obj = _obj(object_name)
    bm = _bm_from_object(obj)
    faces = [bm.faces[i] for i in (sel["faces"] or []) if i < len(bm.faces)]
    if not faces:
        bm.free()
        return {"status": "ok", "selection_id": selection_id, "new_faces": 0}

    ext = bmesh.ops.extrude_face_region(bm, geom=faces)
    new_faces = [g for g in ext["geom"] if isinstance(g, bmesh.types.BMFace)]
    new_verts = [g for g in ext["geom"] if isinstance(g, bmesh.types.BMVert)]

    if new_verts:
        # Centro de masa de los vértices recién extruidos
        cen = Vector((0.0, 0.0, 0.0))
        for v in new_verts:
            cen += v.co
        cen /= float(len(new_verts))
        # Traslación
        bmesh.ops.translate(bm, verts=new_verts, vec=Vector(translate))
        # Escala respecto al centro (2.79-friendly)
        sx, sy, sz = scale_about_center
        T1 = Matrix.Translation(-cen)
        S  = _scale_matrix(sx, sy, sz)
        T2 = Matrix.Translation(cen)
        M = T2 * S * T1
        for v in new_verts:
            v.co = (M * v.co.to_4d()).to_3d()

    if inset and new_faces:
        bmesh.ops.inset_region(bm, faces=new_faces, thickness=float(inset), depth=0.0)

    _bm_to_object(obj, bm)
    bm.free()
    return {"status": "ok", "selection_id": selection_id, "new_faces": len(new_faces)}

@_tool
def cmd_edit_move_verts(object_name, selection_id, translate=(0, 0, 0), scale_about_center=(1, 1, 1)):
    """Mueve/escalado de vértices de una selección (si no hay vértices, usa los de las caras; si no, toda la malla)."""
    sel = _fetch_selection(selection_id)
    if not sel or sel["obj"] != object_name:
        return {"status": "error", "message": "seleccion inválida"}
    obj = _obj(object_name)
    bm = _bm_from_object(obj)
    # Prioriza selección de vértices; si no hay, calcula desde caras; si todo vacío, usa todos.
    if sel.get("verts"):
        vset = set(bm.verts[i] for i in sel["verts"] if i < len(bm.verts))
    else:
        fset = [bm.faces[i] for i in (sel["faces"] or []) if i < len(bm.faces)]
        vset = set([v for f in fset for v in f.verts]) if fset else set(bm.verts)

    if vset:
        cen = Vector((0, 0, 0))
        for v in vset:
            cen += v.co
        cen /= float(len(vset))
        bmesh.ops.translate(bm, verts=list(vset), vec=Vector(translate))
        sx, sy, sz = scale_about_center
        T1 = Matrix.Translation(-cen)
        S  = _scale_matrix(sx, sy, sz)  # 2.79-friendly
        T2 = Matrix.Translation(cen)
        M = T2 * S * T1
        for v in vset:
            v.co = (M * v.co.to_4d()).to_3d()
    _bm_to_object(obj, bm)
    bm.free()
    return {"status": "ok", "moved": len(vset)}

@_tool
def cmd_edit_sculpt_selection(object_name, selection_id, moves):
    """Esculpido paramétrico de vértices (gauss/linear) sobre la selección de caras."""
    sel = _fetch_selection(selection_id)
    if not sel or sel["obj"] != object_name:
        return {"status": "error", "message": "seleccion inválida"}
    obj = _obj(object_name)
    bm = _bm_from_object(obj)
    fset = [bm.faces[i] for i in (sel["faces"] or []) if i < len(bm.faces)]
    vset = set([v for f in fset for v in f.verts]) if fset else set()
    for spec in (moves or []):
        axis = spec.get("axis", "z")
        fn = spec.get("fn", "gauss")
        amp = float(spec.get("amplitude", 0.1))
        if fn == "gauss":
            cy = float(spec.get("center_y", 0.4))
            w = max(1e-6, float(spec.get("width", 0.2)))
            for v in vset:
                t = (v.co.y - cy) / w
                g = math.exp(-0.5 * t * t) * amp
                if axis == "z":
                    v.co.z += g
                elif axis == "y":
                    v.co.y += g
                elif axis == "x":
                    v.co.x += g
        elif fn == "linear":
            ax = spec.get("along", "y")
            center = float(spec.get("center", 0.0))
            slope = float(spec.get("slope", 0.0))
            for v in vset:
                t = getattr(v.co, ax) - center
                delta = slope * t
                if axis == "z":
                    v.co.z += delta
                elif axis == "y":
                    v.co.y += delta
                elif axis == "x":
                    v.co.x += delta
    _bm_to_object(obj, bm)
    bm.free()
    return {"status": "ok", "moved": len(vset)}

@_tool
def cmd_geom_mirror_x(object_name, merge_dist=0.0008):
    """Duplica toda la malla, la espeja en X y suelda la costura (remove doubles)."""
    obj = _obj(object_name)
    bm = _bm_from_object(obj)
    dup = bmesh.ops.duplicate(bm, geom=list(bm.verts) + list(bm.edges) + list(bm.faces))
    new_vs = [g for g in dup["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.scale(bm, verts=new_vs, vec=(-1, 1, 1))
    _remove_doubles(bm, float(merge_dist))
    _bm_to_object(obj, bm)
    bm.free()
    return {"status": "ok"}

@_tool
def cmd_geom_cleanup(object_name, merge_dist=0.0008, recalc=True):
    """Limpieza rápida: remove doubles y recálculo de normales."""
    obj = _obj(object_name)
    bm = _bm_from_object(obj)
    _remove_doubles(bm, float(merge_dist))
    _bm_to_object(obj, bm, recalc_normals=bool(recalc))
    bm.free()
    return {"status": "ok"}

@_tool
def cmd_mesh_stats(object_name):
    """Estadísticas básicas de la malla: triángulos, n-gons y bounding box."""
    obj = _obj(object_name)
    tris = _tri_count(obj)
    ngons = sum(1 for p in obj.data.polygons if len(p.vertices) > 4)
    bbox = _mesh_bbox(obj)
    return {"status": "ok", "tris": tris, "ngons": ngons, "bbox": bbox}

@_tool
def cmd_mesh_validate(object_name, check_self_intersections=False):
    """Valida problemas comunes: aristas no-manifold, n-gons, caras posiblemente invertidas y (opcional) autointersecciones 2D."""
    obj = _obj(object_name)
    if obj is None:
        return {"status": "error", "message": "objeto no encontrado"}
    bm = _bm_from_object(obj)
    non_manifold_edges = sum(1 for e in bm.edges if not e.is_manifold)
    ngons = sum(1 for f in bm.faces if len(f.verts) > 4)
    # Centro aproximado para estimar caras invertidas
    vs = [v.co for v in bm.verts]
    cen = Vector((0, 0, 0))
    if vs:
        for v in vs:
            cen += v
        cen /= float(len(vs))
    flipped = 0
    for f in bm.faces:
        c = f.calc_center_bounds()
        vdir = (c - cen)
        if vdir.length > 1e-9 and f.normal.dot(vdir) < 0:
            flipped += 1

    # Autointersecciones 2D (proyección XY) – chequeo grueso
    selfx = 0
    if check_self_intersections:
        segs = []
        for e in bm.edges:
            a, b = e.verts[0].co, e.verts[1].co
            segs.append(((a.x, a.y), (b.x, b.y)))

        def _ccw(A, B, C):
            return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])

        def _inter(s1, s2):
            A, B = s1
            C, D = s2
            return (_ccw(A, C, D) != _ccw(B, C, D)) and (_ccw(A, B, C) != _ccw(A, B, D))

        n = len(segs)
        for i in range(n):
            for j in range(i + 1, n):
                selfx += 1 if _inter(segs[i], segs[j]) else 0

    bm.free()
    return {"status": "ok",
            "non_manifold_edges": non_manifold_edges,
            "ngons": ngons,
            "flipped_faces_estimate": flipped,
            "self_intersections_xy": selfx}

@_tool
def cmd_similarity_iou_top(object_name, image_path, res=256, margin=0.05, threshold=0.5):
    """Proyecta el mesh en XY, rasteriza y compara con la silueta de una imagen de referencia mediante IoU."""
    obj = _obj(object_name)
    if obj is None:
        return {"status": "error", "message": "objeto no encontrado"}
    mesh_mask = _rasterize_mesh_xy(obj, int(res), float(margin))
    ref_mask = _load_mask_image(image_path, int(res), float(threshold))
    score = _iou(mesh_mask, ref_mask)
    return {"status": "ok", "iou": score}

@_tool
def cmd_similarity_iou_side(object_name, image_path, res=256, margin=0.05, threshold=0.5):
    """Compara la silueta lateral (plano XZ) del objeto con una imagen de referencia usando IoU."""
    obj = _obj(object_name)
    if obj is None:
        return {"status":"error","message":"objeto no encontrado"}
    verts, faces = _mesh_world_verts_faces(obj)
    mesh_mask, _ = _rasterize_verts_faces_plane(verts, faces, plane='XZ', res=int(res), margin=float(margin))
    ref_mask = _load_mask_image(image_path, int(res), float(threshold))
    score = _iou(mesh_mask, ref_mask)
    return {"status":"ok","iou":score}

@_tool
def cmd_similarity_iou_front(object_name, image_path, res=256, margin=0.05, threshold=0.5):
    """Compara la silueta frontal (plano YZ local) con una imagen (IoU)."""
    obj = _obj(object_name)
    if obj is None:
        return {"status":"error","message":"objeto no encontrado"}
    mesh_mask, _ = _rasterize_mesh_plane_local(obj, plane='YZ', res=int(res), margin=float(margin))
    ref_mask = _load_mask_image(image_path, int(res), float(threshold))
    return {"status":"ok","iou": _iou(mesh_mask, ref_mask)}

@_tool
def cmd_similarity_iou_combo(object_name, image_top, image_side, res=256, margin=0.05, threshold=0.5, alpha=0.5):
    """IoU combinado TOP(XY)+SIDE(XZ). alpha pondera TOP (0..1)."""
    a = float(alpha)
    top = cmd_similarity_iou_top(object_name, image_top, res=res, margin=margin, threshold=threshold)
    side = cmd_similarity_iou_side(object_name, image_side, res=res, margin=margin, threshold=threshold)
    if top.get("status")!="ok" or side.get("status")!="ok":
        return {"status":"error","message":"fallo en top o side"}
    combo = a*float(top["iou"]) + (1.0-a)*float(side["iou"])
    return {"status":"ok","iou_top":top["iou"],"iou_side":side["iou"],"iou_combo":combo,"alpha":a}

@_tool
def cmd_similarity_iou_combo3(object_name, image_top, image_side, image_front,
                              res=256, margin=0.05, threshold=0.5,
                              alpha=0.34, beta=0.33, gamma=0.33):
    """IoU combinado para 3 vistas: TOP(XY), SIDE(XZ), FRONT(YZ) con pesos α,β,γ (suman≈1)."""
    top  = cmd_similarity_iou_top(object_name, image_top, res=res, margin=margin, threshold=threshold)
    side = cmd_similarity_iou_side(object_name, image_side, res=res, margin=margin, threshold=threshold)
    frnt = cmd_similarity_iou_front(object_name, image_front, res=res, margin=margin, threshold=threshold)
    if top.get("status")!="ok" or side.get("status")!="ok" or frnt.get("status")!="ok":
        return {"status":"error","message":"fallo en alguna vista"}
    a,b,c = float(alpha), float(beta), float(gamma)
    s = a*float(top["iou"]) + b*float(side["iou"]) + c*float(frnt["iou"])
    return {"status":"ok","iou_top":top["iou"],"iou_side":side["iou"],"iou_front":frnt["iou"],
            "iou_combo3":s,"alpha":a,"beta":b,"gamma":c}

@_tool
def cmd_merge_stitch(object_a, object_b, out_name="Merged", delete="B_inside_A",
                     weld_dist=0.001, res=256, margin=0.03):
    """Fusiona dos mallas en un único objeto (stitch por silueta XY+XZ y soldadura)."""
    ref_name, cut_name = (object_a, object_b) if delete=="B_inside_A" else (object_b, object_a)
    ref = _obj(ref_name); cut = _obj(cut_name)
    if ref is None or cut is None:
        return {"status":"error","message":"alguno de los objetos no existe"}

    vR, fR = _mesh_world_verts_faces(ref)
    mask_xy, bounds_xy = _rasterize_verts_faces_plane(vR, fR, 'XY', res=int(res), margin=float(margin))
    mask_xz, bounds_xz = _rasterize_verts_faces_plane(vR, fR, 'XZ', res=int(res), margin=float(margin))

    vC, fC = _mesh_world_verts_faces(cut)
    keep_face = [True]*len(fC)
    for idx, face in enumerate(fC):
        cx = sum(vC[i].x for i in face)/float(len(face))
        cy = sum(vC[i].y for i in face)/float(len(face))
        cz = sum(vC[i].z for i in face)/float(len(face))
        inside_xy = _mask_sample(mask_xy, bounds_xy, cx, cy)
        inside_xz = _mask_sample(mask_xz, bounds_xz, cx, cz)
        if inside_xy and inside_xz:
            keep_face[idx] = False  # “sobrante” a eliminar

    bm = bmesh.new()
    mapR = [bm.verts.new((co.x,co.y,co.z)) for co in vR]
    for face in fR:
        try:
            bm.faces.new([mapR[i] for i in face])
        except ValueError:
            pass
    mapC = [bm.verts.new((co.x,co.y,co.z)) for co in vC]
    for i, face in enumerate(fC):
        if not keep_face[i]:
            continue
        try:
            bm.faces.new([mapC[j] for j in face])
        except ValueError:
            pass

    _remove_doubles(bm, float(weld_dist))
    bm.edges.ensure_lookup_table()
    border_edges = [e for e in bm.edges if len(e.link_faces)==1]
    if border_edges:
        try:
            bmesh.ops.holes_fill(bm, edges=border_edges)
        except Exception:
            pass

    me = bpy.data.meshes.new(out_name + "Mesh")
    obj = bpy.data.objects.new(out_name, me)
    bpy.context.scene.objects.link(obj)
    _bm_to_object(obj, bm, recalc_normals=True)
    bm.free()
    return {"status":"ok","merged_object":obj.name,"weld_dist":float(weld_dist)}

@_tool
def cmd_mesh_snapshot(object_name):
    """Guarda un snapshot ligero del mesh (lista de vértices y caras) y devuelve un snapshot_id."""
    obj = _obj(object_name)
    if obj is None:
        return {"status": "error", "message": "objeto no encontrado"}
    me = obj.data
    verts = [(v.co.x, v.co.y, v.co.z) for v in me.vertices]
    faces = [tuple(p.vertices) for p in me.polygons]
    sid = _selection_store.get("snapshot_next", 1)
    _selection_store["snapshot_next"] = sid + 1
    if "_snapshots" not in _selection_store:
        _selection_store["_snapshots"] = {}
    _selection_store["_snapshots"][sid] = {"obj": object_name, "verts": verts, "faces": faces}
    return {"status": "ok", "snapshot_id": sid, "verts": len(verts), "faces": len(faces)}

@_tool
def cmd_mesh_restore(snapshot_id, object_name=None):
    """Restaura un snapshot previamente guardado sobre el objeto (si no se indica, usa el original del snapshot)."""
    snaps = _selection_store.get("_snapshots", {})
    snap = snaps.get(int(snapshot_id))
    if not snap:
        return {"status":"error","message":"snapshot no encontrado"}
    obj = _obj(object_name or snap["obj"])
    if obj is None:
        return {"status":"error","message":"objeto no encontrado"}
    bm = bmesh.new()
    bm_verts = [bm.verts.new(v) for v in snap["verts"]]
    for f in snap["faces"]:
        try:
            bm.faces.new([bm_verts[i] for i in f])
        except ValueError:
            pass
    _bm_to_object(obj, bm)
    bm.free()
    return {"status":"ok","restored_to": obj.name}

@_tool
def cmd_mesh_normals_recalc(object_name, ensure_outside=True):
    """Recalcula normales y, si ensure_outside=True, invierte las que miran al centro de masa."""
    obj = _obj(object_name)
    if obj is None:
        return {"status":"error","message":"objeto no encontrado"}
    bm = _bm_from_object(obj)
    try:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    except Exception:
        bm.normal_update()

    flipped = 0
    if ensure_outside:
        vs = [v.co for v in bm.verts]
        if vs:
            cen = Vector((0,0,0))
            for v in vs: cen += v
            cen /= float(len(vs))
            to_flip = []
            for f in bm.faces:
                c = f.calc_center_bounds()
                vdir = (c - cen)
                if vdir.length > 1e-9 and f.normal.dot(vdir) < 0:
                    to_flip.append(f)
            if to_flip:
                try:
                    bmesh.ops.reverse_faces(bm, faces=to_flip)
                    flipped = len(to_flip)
                except Exception:
                    for f in to_flip:
                        f.normal_flip()

    _bm_to_object(obj, bm, recalc_normals=True)
    bm.free()
    return {"status":"ok","flipped":flipped}


# Selección por loops & rings de aristas

def _edge_opposite_in_face(e, f):
    """En un quad f, devuelve la arista opuesta a e (que no comparte vértices)."""
    ev = {e.verts[0], e.verts[1]}
    if len(f.verts) != 4: return None
    for ed in f.edges:
        if ed is e: continue
        if (ed.verts[0] not in ev) and (ed.verts[1] not in ev):
            return ed
    return None

def _collect_edge_ring(bm, seed_edge):
    """Recolecta un 'ring' BFS: aristas opuestas a través de quads contiguos."""
    ring = set()
    q = [seed_edge]
    while q:
        e = q.pop(0)
        if e in ring: continue
        ring.add(e)
        for f in e.link_faces:
            if len(f.verts) != 4: continue
            opp = _edge_opposite_in_face(e, f)
            if opp and opp not in ring:
                q.append(opp)
    return list(ring)

def _step_loop(loop, forward=True):
    """Paso de arista para un edge-loop a través de quads:
       l -> (dos pasos en face) -> radial al face vecino.
    """
    f = loop.face
    if not f or len(f.verts)!=4:
        return None
    nxt = loop.link_loop_next.link_loop_next if forward else loop.link_loop_prev.link_loop_prev
    if nxt is None: return None
    nxt = nxt.link_loop_radial_next
    return nxt

def _collect_edge_loop(bm, seed_edge):
    """Recolecta edge-loop usando loops radiales (ambas direcciones)."""
    edges = set([seed_edge])
    for l in seed_edge.link_loops:
        # adelante
        cur = l
        while True:
            cur = _step_loop(cur, True)
            if not cur or cur.edge in edges:
                break
            edges.add(cur.edge)
        # atrás
        cur = l
        while True:
            cur = _step_loop(cur, False)
            if not cur or cur.edge in edges:
                break
            edges.add(cur.edge)
    return list(edges)

@_tool
def cmd_select_edge_loop_from_edge(object_name, edge_index):
    """Devuelve la selección de un edge-loop partiendo de una arista índice."""
    obj = _obj(object_name)
    bm = _bm_from_object(obj)
    if edge_index < 0 or edge_index >= len(bm.edges):
        bm.free(); return {"status":"error","message":"edge_index fuera de rango"}
    loop_edges = _collect_edge_loop(bm, bm.edges[edge_index])
    ids = [e.index for e in loop_edges]
    sid = _store_selection(obj.name, edges_idx=ids)
    bm.free()
    return {"status":"ok","selection_id":sid,"count":len(ids)}

@_tool
def cmd_select_edge_ring_from_edge(object_name, edge_index):
    """Devuelve la selección de un edge-ring partiendo de una arista índice."""
    obj = _obj(object_name)
    bm = _bm_from_object(obj)
    if edge_index < 0 or edge_index >= len(bm.edges):
        bm.free(); return {"status":"error","message":"edge_index fuera de rango"}
    ring_edges = _collect_edge_ring(bm, bm.edges[edge_index])
    ids = [e.index for e in ring_edges]
    sid = _store_selection(obj.name, edges_idx=ids)
    bm.free()
    return {"status":"ok","selection_id":sid,"count":len(ids)}


# Loop cut / subdividir anillos

@_tool
def cmd_mesh_loop_insert(object_name, edges=None, selection_id=None, cuts=1, smooth=0.0):
    """Inserta cortes a lo largo de un conjunto de aristas (loop/ring)."""
    obj = _obj(object_name)
    bm = _bm_from_object(obj)
    eds = []
    if selection_id:
        sel = _fetch_selection(selection_id) or {}
        if sel.get("obj") == object_name:
            eds = [bm.edges[i] for i in (sel.get("edges") or []) if i < len(bm.edges)]
    if not eds and edges:
        eds = [bm.edges[i] for i in edges if i < len(bm.edges)]
    if not eds:
        bm.free(); return {"status":"error","message":"sin aristas válidas"}
    res = bmesh.ops.subdivide_edges(
        bm, edges=eds, cuts=int(cuts),
        use_grid_fill=False, smooth=float(smooth)
    )
    _bm_to_object(obj, bm)
    bm.free()
    nv = len(res.get('geom_inner', []))
    return {"status":"ok","new_elements": nv}

# Bevel paramétrico (sin bpy.ops)

def _edges_by_sharp(bm, angle_deg):
    th = math.cos(math.radians(float(angle_deg)))
    out = []
    for e in bm.edges:
        fs = list(e.link_faces)
        if len(fs)==2:
            d = fs[0].normal.dot(fs[1].normal)
            if d <= th:  # ángulo >= threshold
                out.append(e)
    return out

def _valid_bevel_geom(bm, geom, min_len=1e-5):
    """Filtra geometría peligrosa: edges muy cortas o no-manifold, y vértices sin soporte."""
    import bmesh as _bmesh
    out = []
    for g in geom:
        if isinstance(g, _bmesh.types.BMEdge):
            if len(g.link_faces) == 2:
                if (g.verts[0].co - g.verts[1].co).length > float(min_len):
                    out.append(g)
        elif isinstance(g, _bmesh.types.BMVert):
            # vértice válido si tiene alguna arista manifold razonable
            ok = False
            for e in g.link_edges:
                if len(e.link_faces) == 2 and (e.verts[0].co - e.verts[1].co).length > float(min_len):
                    ok = True; break
            if ok:
                out.append(g)
    return out


@_tool
def cmd_mesh_bevel(object_name, edges=None, verts=None, selection_id=None,
                   offset=0.01, segments=2, profile=0.7, clamp=True,
                   auto_sharp_angle=None):
    """
    Bevel robusto usando bmesh.ops.bevel, con filtrado de geometría y fallback si falla.
    """
    obj = _obj(object_name)
    bm = _bm_from_object(obj)

    # Construir conjunto inicial
    geom = []
    if auto_sharp_angle is not None:
        geom.extend(_edges_by_sharp(bm, float(auto_sharp_angle)))
    if selection_id:
        sel = _fetch_selection(selection_id) or {}
        if sel.get("obj") == object_name:
            geom.extend([bm.edges[i] for i in (sel.get("edges") or []) if 0 <= i < len(bm.edges)])
            geom.extend([bm.verts[i] for i in (sel.get("verts") or []) if 0 <= i < len(bm.verts)])
    if edges:
        geom.extend([bm.edges[i] for i in edges if 0 <= i < len(bm.edges)])
    if verts:
        geom.extend([bm.verts[i] for i in verts if 0 <= i < len(bm.verts)])

    # Filtrar aristas/vértices peligrosos
    geom = list(set(_valid_bevel_geom(bm, geom, min_len=1e-6)))
    if not geom:
        bm.free()
        return {"status":"error","message":"sin geometría válida para bevel (posible no-manifold o aristas ~0)"}

    # Limpieza previa: disolver degenerados muy cortos
    try:
        bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-6)
    except Exception:
        pass

    # Intento principal
    ok = False
    note = ""
    try:
        res = bmesh.ops.bevel(
            bm, geom=geom,
            offset=float(offset), segments=int(segments), profile=float(profile),
            clamp_overlap=bool(clamp)
        )
        ok = True
    except Exception as e:
        # Fallback: segmentos 1 y offset reducido
        try:
            res = bmesh.ops.bevel(
                bm, geom=geom,
                offset=min(float(offset), 0.004), segments=1, profile=0.7,
                clamp_overlap=True
            )
            ok = True
            note = "fallback_segments1"
        except Exception as e2:
            bm.free()
            return {"status":"error","message":"bevel falló incluso con fallback", "detail":"{} / {}".format(e, e2)}

    # Post: quitar dobles pequeños y actualizar
    try:
        _remove_doubles(bm, 0.0005)
    except Exception:
        pass
    _bm_to_object(obj, bm)
    bm.free()
    return {"status":"ok","beveled": len(res.get('faces_out', [])), "note": note}



# Geodesic select (distancia sobre superficie)

@_tool
def cmd_select_geodesic(object_name, seed_vert=None, selection_id=None, radius=0.25):
    """Selecciona vértices a distancia geodésica <= radius desde semilla(s)."""
    obj = _obj(object_name)
    bm = _bm_from_object(obj)
    seeds = []
    if seed_vert is not None and 0 <= int(seed_vert) < len(bm.verts):
        seeds.append(bm.verts[int(seed_vert)])
    if selection_id:
        sel = _fetch_selection(selection_id) or {}
        if sel.get("obj")==object_name:
            seeds.extend([bm.verts[i] for i in (sel.get("verts") or []) if i < len(bm.verts)])
    if not seeds:
        bm.free(); return {"status":"error","message":"sin semillas"}
    import heapq
    dist = {v: 0.0 for v in seeds}
    pq = [(0.0, v) for v in seeds]
    seen = set(seeds)
    while pq:
        d, v = heapq.heappop(pq)
        if d > float(radius): break
        for e in v.link_edges:
            w = e.other_vert(v)
            nd = d + (w.co - v.co).length
            if nd <= float(radius) and (w not in dist or nd < dist[w]):
                dist[w] = nd
                heapq.heappush(pq, (nd, w))
                seen.add(w)
    ids = [v.index for v in seen]
    sid = _store_selection(obj.name, verts_idx=ids)
    bm.free()
    return {"status":"ok","selection_id":sid,"count":len(ids)}


# Snap a silueta (proyección 2D guiada por imagen)

@_tool
def cmd_edit_snap_to_silhouette(object_name, selection_id, plane='XY', image_path=None,
                                strength=0.5, iterations=8, step=1.0, res=256, margin=0.05, threshold=0.5):
    """Atrae vértices seleccionados hacia el borde de la silueta 2D (imagen) en el plano dado."""
    if not image_path:
        return {"status":"error","message":"image_path requerido"}
    obj = _obj(object_name)
    bm = _bm_from_object(obj)
    sel = _fetch_selection(selection_id) or {}
    if sel.get("obj") != object_name:
        bm.free(); return {"status":"error","message":"selección inválida"}
    vset = [bm.verts[i] for i in (sel.get("verts") or []) if i < len(bm.verts)]
    if not vset:
        # si no hay vértices en la selección, derivar de las caras
        fset = [bm.faces[i] for i in (sel.get("faces") or []) if i < len(bm.faces)]
        vset = list({v for f in fset for v in f.verts})
    if not vset:
        bm.free(); return {"status":"error","message":"no hay vértices a snapear"}

    mask_ref = _load_mask_image(image_path, int(res), float(threshold))
    mask_mesh, bounds = _rasterize_mesh_plane_local(obj, plane=plane, res=int(res), margin=float(margin))
    minx,maxx,miny,maxy = bounds['minx'],bounds['maxx'],bounds['miny'],bounds['maxy']
    sx = (res-1)/(maxx-minx); sy = (res-1)/(maxy-miny)
    cell = max((maxx-minx)/(res-1), (maxy-miny)/(res-1))
    step_len = float(step) * cell
    stren = float(strength)

    moved = 0
    for v in vset:
        u0,v0 = _get_uv_from_vec(v.co, plane)
        u, w = u0, v0
        for _ in range(int(iterations)):
            ix = int((u - minx)*sx + 0.5)
            iy = int((w - miny)*sy + 0.5)
            inside = mask_ref[iy][ix]
            gx, gy = _mask_grad(mask_ref, ix, iy)
            gnorm = math.hypot(gx, gy)
            if gnorm < 1e-6:
                break
            sgn = 1.0 if not inside else -1.0
            du = sgn * (gx/gnorm) * step_len
            dv = sgn * (gy/gnorm) * step_len
            u += du; w += dv
        # aplicar fracción (strength) del desplazamiento
        du_fin, dv_fin = (u - u0)*stren, (w - v0)*stren
        _set_uv_on_vec(v.co, plane, u0 + du_fin, v0 + dv_fin)
        moved += 1

    _bm_to_object(obj, bm)
    bm.free()
    return {"status":"ok","moved":moved}


# Landmarks 2D→3D (puntos guía)

@_tool
def cmd_constraint_landmarks_apply(object_name, plane='XY', points=None, falloff='gauss'):
    """Aplica landmarks 2D (uv en 0..1) con radio/strength en el plano dado."""
    if not points:
        return {"status":"error","message":"sin puntos"}
    obj = _obj(object_name)
    bm = _bm_from_object(obj)
    bounds = _bounds_on_plane_local(obj, plane)
    minx,maxx,miny,maxy = bounds['minx'],bounds['maxx'],bounds['miny'],bounds['maxy']
    W = (maxx-minx); H = (maxy-miny)
    moved = 0
    for v in bm.verts:
        u, w = _get_uv_from_vec(v.co, plane)
        un = 0.0 if W<1e-9 else (u - minx)/W
        wn = 0.0 if H<1e-9 else (w - miny)/H
        du_sum = dv_sum = 0.0
        wt_sum = 0.0
        for p in points:
            uv = p.get("uv",[0.5,0.5])
            rad = float(p.get("radius",0.1))
            stren = float(p.get("strength",0.8))
            dx = un - float(uv[0]); dy = wn - float(uv[1])
            d = math.hypot(dx,dy)
            if d > rad: continue
            if falloff == 'gauss':
                sigma = rad/2.0 if rad>1e-9 else 1e-3
                wgt = math.exp(-0.5*(d/sigma)**2) * stren
            else:
                wgt = (1.0 - d/rad) * stren
            target_u = minx + float(uv[0]) * W
            target_w = miny + float(uv[1]) * H
            du_sum += (target_u - u) * wgt
            dv_sum += (target_w - w) * wgt
            wt_sum += wgt
        if wt_sum > 0:
            _set_uv_on_vec(v.co, plane, u + du_sum/wt_sum, w + dv_sum/wt_sum)
            moved += 1
    _bm_to_object(obj, bm)
    bm.free()
    return {"status":"ok","moved":moved}


# Simetrías avanzadas (plano arbitrario y radial)

@_tool
def cmd_geom_mirror_plane(object_name, plane_point=(0,0,0), plane_normal=(1,0,0), merge_dist=0.0008):
    """Duplica y refleja toda la malla respecto a un plano arbitrario (punto+normal en espacio local)."""
    obj = _obj(object_name)
    bm = _bm_from_object(obj)
    P = Vector(plane_point)
    n = Vector(plane_normal)
    try: n.normalize()
    except: return {"status":"error","message":"normal inválida"}
    # Duplicar
    dup = bmesh.ops.duplicate(bm, geom=list(bm.verts) + list(bm.edges) + list(bm.faces))
    new_vs = [g for g in dup["geom"] if isinstance(g, bmesh.types.BMVert)]
    # Reflexión (Householder): v' = P + (I - 2nn^T)(v - P)
    I = Matrix.Identity(3)
    H = I - 2.0 * Matrix((
        (n.x*n.x, n.x*n.y, n.x*n.z),
        (n.y*n.x, n.y*n.y, n.y*n.z),
        (n.z*n.x, n.z*n.y, n.z*n.z),
    ))
    for v in new_vs:
        p = v.co - P
        r = Vector((H[0][0]*p.x + H[0][1]*p.y + H[0][2]*p.z,
                    H[1][0]*p.x + H[1][1]*p.y + H[1][2]*p.z,
                    H[2][0]*p.x + H[2][1]*p.y + H[2][2]*p.z))
        v.co = P + r
    _remove_doubles(bm, float(merge_dist))
    _bm_to_object(obj, bm)
    bm.free()
    return {"status":"ok"}

@_tool
def cmd_geom_symmetry_radial(object_name, axis='Z', count=6, merge_dist=0.0008):
    """Simetría radial n-fold duplicando y rotando la malla alrededor del eje local indicado."""
    obj = _obj(object_name)
    bm = _bm_from_object(obj)
    axis = axis.upper()
    ax = {'X':Vector((1,0,0)), 'Y':Vector((0,1,0)), 'Z':Vector((0,0,1))}.get(axis, Vector((0,0,1)))
    copies = []
    base_geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
    for k in range(1, int(count)):
        ang = (2.0*math.pi)*k/float(count)
        dup = bmesh.ops.duplicate(bm, geom=base_geom)
        new_vs = [g for g in dup["geom"] if isinstance(g, bmesh.types.BMVert)]
        R = Matrix.Rotation(ang, 4, ax)
        for v in new_vs:
            v.co = (R * v.co.to_4d()).to_3d()
        copies.extend(new_vs)
    _remove_doubles(bm, float(merge_dist))
    _bm_to_object(obj, bm)
    bm.free()
    return {"status":"ok","instances":int(count)}


# Topología y reparación

@_tool
def cmd_mesh_triangulate_beautify(object_name):
    """Triangula malla y aplica 'beautify' para mejorar calidad angular."""
    obj = _obj(object_name)
    bm = _bm_from_object(obj)
    bmesh.ops.triangulate(bm, faces=bm.faces, quad_method=0, ngon_method=0)  # BEAUTY/BEAUTY
    try:
        bmesh.ops.beautify_fill(bm, edges=bm.edges)
    except Exception:
        pass
    _bm_to_object(obj, bm)
    bm.free()
    return {"status":"ok"}

@_tool
def cmd_mesh_join_quads(object_name, angle_face=0.1, angle_shape=0.5):
    """Une triángulos coplanares para formar quads cuando es posible."""
    obj = _obj(object_name)
    bm = _bm_from_object(obj)
    bmesh.ops.join_triangles(bm, faces=bm.faces,
                             angle_face_threshold=float(angle_face),
                             angle_shape_threshold=float(angle_shape))
    _bm_to_object(obj, bm)
    bm.free()
    return {"status":"ok"}

@_tool
def cmd_mesh_bridge_loops(object_name, loops):
    """Puentea bordes: 'loops' es lista de listas de índices de arista."""
    obj = _obj(object_name)
    bm = _bm_from_object(obj)
    eds = []
    for L in (loops or []):
        eds.extend([bm.edges[i] for i in L if i < len(bm.edges)])
    if not eds:
        bm.free(); return {"status":"error","message":"sin aristas para bridge"}
    bmesh.ops.bridge_loops(bm, edges=eds)
    _bm_to_object(obj, bm)
    bm.free()
    return {"status":"ok"}

@_tool
def cmd_mesh_fill_holes(object_name):
    """Rellena agujeros detectando bordes frontera (len(link_faces)==1)."""
    obj = _obj(object_name)
    bm = _bm_from_object(obj)
    bm.edges.ensure_lookup_table()
    border_edges = [e for e in bm.edges if len(e.link_faces)==1]
    if border_edges:
        try:
            bmesh.ops.holes_fill(bm, edges=border_edges)
        except Exception:
            pass
    _bm_to_object(obj, bm)
    bm.free()
    return {"status":"ok","filled": len(border_edges)}






# Macros
@_tool
def cmd_macro_nose(object_name, y_min=0.85, push_y=0.18, sharpen=0.35):
    """Macro: extruye la nariz hacia +Y y afila en X un porcentaje (sharpen)."""
    sel = cmd_select_faces_by_range(object_name, [{"axis": "y", "min": float(y_min)}])
    if sel.get("status") != "ok":
        return sel
    sid = sel.get("selection_id", 0)
    return cmd_edit_extrude_selection(object_name, sid,
                                      translate=(0, float(push_y), 0),
                                      scale_about_center=(1.0 - float(sharpen), 1, 1),
                                      inset=0.0)

@_tool
def cmd_macro_pods(object_name, y0=0.15, y1=0.65, x_min=0.30, push_x=0.18, squash_z=0.12):
    """Macro: crea pods laterales en la banda media extruyendo en +X y aplastando levemente en Z."""
    sel = cmd_select_faces_by_range(object_name, [
        {"axis": "y", "min": float(y0), "max": float(y1)},
        {"axis": "x", "min": float(x_min)}
    ])
    if sel.get("status") != "ok":
        return sel
    sid = sel.get("selection_id", 0)
    return cmd_edit_extrude_selection(object_name, sid,
                                      translate=(float(push_x), 0, 0),
                                      scale_about_center=(1, 1, 1.0 - float(squash_z)))

@_tool
def cmd_macro_tail(object_name, y_max=-0.80, pull_y=0.16, inset=0.02):
    """Macro: extruye la cola hacia -Y y realiza un inset para sugerir la tobera."""
    sel = cmd_select_faces_by_range(object_name, [{"axis": "y", "max": float(y_max)}])
    if sel.get("status") != "ok":
        return sel
    sid = sel.get("selection_id", 0)
    return cmd_edit_extrude_selection(object_name, sid,
                                      translate=(0, -float(pull_y), 0),
                                      inset=float(inset))

# =====================================================================================
# Servidor WebSocket
# =====================================================================================

async def handler(websocket, path=None):
    """Bucle principal del servidor: recibe comandos JSON, los ejecuta y devuelve un ACK JSON."""
    print("Cliente de WebSocket conectado.")
    try:
        while True:
            try:
                message = await websocket.recv()
            except ConnectionClosed:
                print("Conexión cerrada de forma normal.")
                break
            except Exception as e:
                print("Excepción en recv(): {0}".format(e))
                traceback.print_exc()
                break

            print("Mensaje recibido: {0}".format(message))

            try:
                data = json.loads(message)
            except Exception:
                data = {"command": "echo", "message": message}

            cmd = data.get("command")
            p = data.get("params", {}) or {}

                        # --- Enqueue to main-thread pump and wait for result (non-blocking) ---
            # Optional backpressure: refuse if queue is too large
            max_tasks = int(os.environ.get("MCP_MAX_TASKS", "128"))
            with _TASKS_LOCK:
                if len(_TASKS) >= max_tasks:
                    ack = {"status": "error", "message": "server busy: too many queued tasks"}
                else:
                    t = _Task(cmd, p)
                    _TASKS.append(t)
                    tref = t
            if 'ack' not in locals():
                loop_local = asyncio.get_event_loop()
                try:
                    ok = await asyncio.wait_for(loop_local.run_in_executor(None, tref.event.wait, float(p.get("timeout", 30.0))), timeout=float(p.get("timeout", 31.0)))
                    if not ok:
                        ack = {"status": "error", "message": "timeout esperando ejecución en hilo principal"}
                    else:
                        ack = tref.result or {"status": "error", "message": "sin resultado"}
                except asyncio.TimeoutError:
                    ack = {"status": "error", "message": "timeout esperando ejecución en hilo principal"}            
                except Exception as exc:
                    print("[DEBUG] Error procesando '{0}': {1}".format(cmd, exc))
                    traceback.print_exc()
                    ack = {"status": "error", "message": str(exc), "trace": traceback.format_exc()}

            try:
                payload = json.dumps(ack)
            except Exception as exc:
                print("[DEBUG] json.dumps falló: {0}".format(exc))
                traceback.print_exc()
                payload = json.dumps({"status": "error", "message": "json serialization error"})

            try:
                await websocket.send(payload)
            except ConnectionClosed:
                print("Cliente cerró antes del ACK.")
                break
            except Exception as exc:
                print("[DEBUG] Excepción en send(): {0}".format(exc))
                traceback.print_exc()
                break

    except Exception as e:
        print("Excepción en handler: {0}".format(e))
        traceback.print_exc()
    finally:
        print("Cliente de WebSocket desconectado.")

def run_server():
    """Crea el event loop y ejecuta el servidor websockets en el hilo actual."""
    global loop, server
    if websockets is None:
        print("Instala websockets==7.0 en el Python de Blender.")
        return

    async def _serve():
        return await websockets.serve(
            handler, "127.0.0.1", 8002,
            ping_interval=20, ping_timeout=20, max_queue=1, close_timeout=0
        )

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        server = loop.run_until_complete(_serve())
        print("Servidor WebSocket iniciado en 127.0.0.1:8002 (websockets {0})".format(
            getattr(websockets, "__version__", "?")))
        loop.run_forever()
    except Exception as e:
        print("Error al iniciar/ejecutar el servidor: {0}".format(e))
        traceback.print_exc()
    finally:
        try:
            if server is not None:
                server.close()
                loop.run_until_complete(server.wait_closed())
        except Exception as e:
            print("Error cerrando el servidor: {0}".format(e))
            traceback.print_exc()
        try:
            loop.close()
        except Exception:
            pass
        print("Bucle de eventos detenido.")

def start_server():
    """Lanza el servidor en un hilo daemon (llamar desde register() del add-on)."""
    global server_thread
    if server_thread is None or not server_thread.is_alive():
        server_thread = threading.Thread(target=run_server)
        server_thread.daemon = True
        server_thread.start()
        print("Hilo del servidor WebSocket iniciado.")

def stop_server():
    """Detiene el event loop y espera al hilo del servidor (llamar desde unregister())."""
    global server_thread, loop
    if loop is not None:
        try:
            loop.call_soon_threadsafe(loop.stop)
        except Exception:
            traceback.print_exc()
    if server_thread is not None:
        try:
            server_thread.join(timeout=2.0)
        except Exception:
            traceback.print_exc()
    server_thread = None



def register():
    try:
        bpy.utils.register_class(MCP_OT_TaskPump)
    except Exception:
        pass
    # Try to start the pump right away
    try:
        bpy.ops.wm.mcp_task_pump()
    except Exception:
        # It may fail if no window context; it's fine – user can run it from the UI or call again later.
        pass

def unregister():
    try:
        bpy.utils.unregister_class(MCP_OT_TaskPump)
    except Exception:
        pass
