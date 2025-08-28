# Blender 2.79 – WebSocket server + API de modelado (bmesh-only)
# Requiere websockets==7.0 (Python 3.5)
# https://docs.blender.org/api/2.79b/
#
# Comandos soportados (JSON):
#  - identify
#  - execute_python / execute_python_file
#  - export_fbx
#  - geom.create_base
#  - select.faces_by_range / select.faces_in_bbox / select.faces_by_normal / select.grow / select.verts_by_curvature
#  - edit.extrude_selection / edit.move_verts / edit.sculpt_selection
#  - geom.mirror_x / geom.cleanup
#  - mesh.stats / mesh.validate
#  - mesh.snapshot / mesh.restore
#  - similarity.iou_top
#
# Todos los comandos de modelado usan bmesh + API de datos (SIN cambiar de modo ni usar bpy.ops de edición).

from __future__ import print_function

import asyncio
import threading
import json
import os
import importlib
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
    """Ejecuta código Python arbitrario en un entorno controlado y captura stdout/stderr."""
    local_env = {"bpy": bpy, "bmesh": bmesh, "Vector": Vector, "Matrix": Matrix, "math": math}
    stdout_io = io.StringIO()
    stderr_io = io.StringIO()
    try:
        from contextlib import redirect_stdout, redirect_stderr
        with redirect_stdout(stdout_io), redirect_stderr(stderr_io):
            exec(code, local_env, local_env)
    except Exception as exc:
        print("execute_python error: {0}".format(exc))
        traceback.print_exc()
    return stdout_io.getvalue(), stderr_io.getvalue()

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

def _store_selection(obj_name, faces_idx=None, verts_idx=None):
    """Guarda una selección efímera (caras o vértices) y devuelve un selection_id."""
    sid = _selection_store["next_id"]
    _selection_store["next_id"] += 1
    _selection_store["selections"][sid] = {
        "obj": obj_name,
        "faces": faces_idx or [],
        "verts": verts_idx or []
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

# =====================================================================================
# Comandos de modelado: creación, selección, edición, macros y validación
# =====================================================================================

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
        # Escala respecto al centro
        sx, sy, sz = scale_about_center
        T1 = Matrix.Translation(-cen)
        S = Matrix.Diagonal((sx, sy, sz, 1.0))
        T2 = Matrix.Translation(cen)
        M = T2 * S * T1
        for v in new_verts:
            v.co = (M * v.co.to_4d()).to_3d()

    if inset and new_faces:
        bmesh.ops.inset_region(bm, faces=new_faces, thickness=float(inset), depth=0.0)

    _bm_to_object(obj, bm)
    bm.free()
    # Tip: re-seleccionar por rango en la siguiente llamada; devolvemos conteo
    return {"status": "ok", "selection_id": selection_id, "new_faces": len(new_faces)}

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
        S = Matrix.Diagonal((sx, sy, sz, 1))
        T2 = Matrix.Translation(cen)
        M = T2 * S * T1
        for v in vset:
            v.co = (M * v.co.to_4d()).to_3d()
    _bm_to_object(obj, bm)
    bm.free()
    return {"status": "ok", "moved": len(vset)}

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

def cmd_geom_cleanup(object_name, merge_dist=0.0008, recalc=True):
    """Limpieza rápida: remove doubles y recálculo de normales."""
    obj = _obj(object_name)
    bm = _bm_from_object(obj)
    _remove_doubles(bm, float(merge_dist))
    _bm_to_object(obj, bm, recalc_normals=bool(recalc))
    bm.free()
    return {"status": "ok"}

def cmd_mesh_stats(object_name):
    """Estadísticas básicas de la malla: triángulos, n-gons y bounding box."""
    obj = _obj(object_name)
    tris = _tri_count(obj)
    ngons = sum(1 for p in obj.data.polygons if len(p.vertices) > 4)
    bbox = _mesh_bbox(obj)
    return {"status": "ok", "tris": tris, "ngons": ngons, "bbox": bbox}

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

# =====================================================================================
# Similitud IoU con silueta 2D (vista superior)
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

def _load_mask_image(path, res=256, threshold=0.5):
    """Carga una imagen y la convierte en máscara booleana (umbral por luminancia) reescalada a res×res."""
    try:
        img = bpy.data.images.load(path)
    except Exception as e:
        raise RuntimeError("No se pudo cargar la imagen de referencia: {0}".format(e))
    w, h = img.size
    px = list(img.pixels)  # RGBA floats

    def sample(u, v):
        # nearest-neighbor
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

def cmd_similarity_iou_top(object_name, image_path, res=256, margin=0.05, threshold=0.5):
    """Proyecta el mesh en XY, rasteriza y compara con la silueta de una imagen de referencia mediante IoU."""
    obj = _obj(object_name)
    if obj is None:
        return {"status": "error", "message": "objeto no encontrado"}
    mesh_mask = _rasterize_mesh_xy(obj, int(res), float(margin))
    ref_mask = _load_mask_image(image_path, int(res), float(threshold))
    score = _iou(mesh_mask, ref_mask)
    return {"status": "ok", "iou": score}


# --- Rasterizado genérico a un plano con vértices en MUNDO ---
def _mesh_world_verts_faces(obj):
    """Devuelve (verts_world, faces_idx) del objeto."""
    me = obj.data
    M = obj.matrix_world
    verts = [(M * v.co.to_4d()).to_3d() for v in me.vertices]
    faces = [tuple(p.vertices) for p in me.polygons]
    return verts, faces

def _rasterize_verts_faces_plane(verts, faces, plane='XY', res=256, margin=0.05):
    """Rasteriza un mesh dado por (verts, faces) en el plano indicado ('XY' o 'XZ').
    Devuelve (mask_bool_2D, bounds_dict) donde bounds={'minx','maxx','miny','maxy'} en el plano elegido."""
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
    # fuera de rango => False
    if x < minx or x > maxx or y < miny or y > maxy:
        return False
    # mapeo a píxel (nearest)
    sx = (res_x-1)/(maxx-minx); sy = (res_y-1)/(maxy-miny)
    ix = int((x-minx)*sx + 0.5); iy = int((y-miny)*sy + 0.5)
    ix = max(0, min(res_x-1, ix)); iy = max(0, min(res_y-1, iy))
    return bool(mask[iy][ix])



def cmd_similarity_iou_side(object_name, image_path, res=256, margin=0.05, threshold=0.5):
    """Compara la silueta lateral (plano XZ) del objeto con una imagen de referencia usando IoU."""
    obj = _obj(object_name)
    if obj is None:
        return {"status":"error","message":"objeto no encontrado"}

    # malla → mundo → rasterizar en XZ
    verts, faces = _mesh_world_verts_faces(obj)
    mesh_mask, _ = _rasterize_verts_faces_plane(verts, faces, plane='XZ', res=int(res), margin=float(margin))

    # imagen → máscara
    ref_mask = _load_mask_image(image_path, int(res), float(threshold))
    score = _iou(mesh_mask, ref_mask)
    return {"status":"ok","iou":score}

def cmd_similarity_iou_combo(object_name, image_top, image_side, res=256, margin=0.05, threshold=0.5, alpha=0.5):
    """IoU combinado TOP(XY)+SIDE(XZ). alpha pondera TOP (0..1)."""
    a = float(alpha)
    top = cmd_similarity_iou_top(object_name, image_top, res=res, margin=margin, threshold=threshold)
    side = cmd_similarity_iou_side(object_name, image_side, res=res, margin=margin, threshold=threshold)
    if top.get("status")!="ok" or side.get("status")!="ok":
        return {"status":"error","message":"fallo en top o side"}
    combo = a*float(top["iou"]) + (1.0-a)*float(side["iou"])
    return {"status":"ok","iou_top":top["iou"],"iou_side":side["iou"],"iou_combo":combo,"alpha":a}

# =====================================================================================
# Merge
# =====================================================================================


def cmd_merge_stitch(object_a, object_b, out_name="Merged", delete="B_inside_A",
                     weld_dist=0.001, res=256, margin=0.03):
    """Fusiona dos mallas en un único objeto:
       - Calcula máscaras TOP(XY) y SIDE(XZ) del objeto de referencia.
       - Elimina de la otra malla las caras cuyo centro cae DENTRO de ambas máscaras (XY y XZ).
       - Concatena ambas geometrías en un solo bmesh en coordenadas de mundo.
       - 'Cose' soldando vértices cercanos (remove doubles) y rellena agujeros si es necesario.

       Params:
         delete: 'B_inside_A' (por defecto) elimina el interior de B respecto a A;
                 'A_inside_B' elimina el interior de A respecto a B.
    """
    ref_name, cut_name = (object_a, object_b) if delete=="B_inside_A" else (object_b, object_a)
    ref = _obj(ref_name); cut = _obj(cut_name)
    if ref is None or cut is None:
        return {"status":"error","message":"alguno de los objetos no existe"}

    # Máscaras del REF en XY y XZ (mundo)
    vR, fR = _mesh_world_verts_faces(ref)
    mask_xy, bounds_xy = _rasterize_verts_faces_plane(vR, fR, 'XY', res=int(res), margin=float(margin))
    mask_xz, bounds_xz = _rasterize_verts_faces_plane(vR, fR, 'XZ', res=int(res), margin=float(margin))

    # Copia filtrada del CUT: descarta caras cuyo centro está dentro de ambas máscaras
    vC, fC = _mesh_world_verts_faces(cut)
    keep_face = [True]*len(fC)
    for idx, face in enumerate(fC):
        # centro de cara en mundo
        cx = sum(vC[i].x for i in face)/float(len(face))
        cy = sum(vC[i].y for i in face)/float(len(face))
        cz = sum(vC[i].z for i in face)/float(len(face))
        inside_xy = _mask_sample(mask_xy, bounds_xy, cx, cy)
        inside_xz = _mask_sample(mask_xz, bounds_xz, cx, cz)
        if inside_xy and inside_xz:
            keep_face[idx] = False  # “sobrante” a eliminar

    # Construcción del BM combinado
    bm = bmesh.new()
    # A) añadir REF
    mapR = [bm.verts.new((co.x,co.y,co.z)) for co in vR]
    for face in fR:
        try:
            bm.faces.new([mapR[i] for i in face])
        except ValueError:
            pass
    # B) añadir CUT filtrado
    mapC = [bm.verts.new((co.x,co.y,co.z)) for co in vC]
    for i, face in enumerate(fC):
        if not keep_face[i]:
            continue
        try:
            bm.faces.new([mapC[j] for j in face])
        except ValueError:
            pass

    # Soldadura de vértices y cierre de agujeros simples
    _remove_doubles(bm, float(weld_dist))
    bm.edges.ensure_lookup_table()
    border_edges = [e for e in bm.edges if len(e.link_faces)==1]
    if border_edges:
        try:
            bmesh.ops.holes_fill(bm, edges=border_edges)
        except Exception:
            pass

    # Volcado a un nuevo objeto
    me = bpy.data.meshes.new(out_name + "Mesh")
    obj = bpy.data.objects.new(out_name, me)
    bpy.context.scene.objects.link(obj)
    _bm_to_object(obj, bm, recalc_normals=True)
    bm.free()
    return {"status":"ok","merged_object":obj.name,"weld_dist":float(weld_dist)}



# =====================================================================================
# Snapshots / Undo simple (en memoria)
# =====================================================================================

_snapshots = {"next": 1, "store": {}}

def cmd_mesh_snapshot(object_name):
    """Guarda un snapshot ligero del mesh (lista de vértices y caras) y devuelve un snapshot_id."""
    obj = _obj(object_name)
    if obj is None:
        return {"status": "error", "message": "objeto no encontrado"}
    me = obj.data
    verts = [(v.co.x, v.co.y, v.co.z) for v in me.vertices]
    faces = [tuple(p.vertices) for p in me.polygons]
    sid = _snapshots["next"]
    _snapshots["next"] += 1
    _snapshots["store"][sid] = {"obj": object_name, "verts": verts, "faces": faces}
    return {"status": "ok", "snapshot_id": sid, "verts": len(verts), "faces": len(faces)}

def cmd_mesh_restore(snapshot_id, object_name=None):
    """Restaura un snapshot previamente guardado sobre el objeto (si no se indica, usa el original del snapshot)."""
    snap = _snapshots["store"].get(int(snapshot_id))
    if not snap:
        return {"status": "error", "message": "snapshot no encontrado"}
    obj = _obj(object_name or snap["obj"])
    if obj is None:
        return {"status": "error", "message": "objeto no encontrado"}
    bm = bmesh.new()
    bm_verts = [bm.verts.new(v) for v in snap["verts"]]
    for f in snap["faces"]:
        try:
            bm.faces.new([bm_verts[i] for i in f])
        except ValueError:
            # cara duplicada ya creada
            pass
    _bm_to_object(obj, bm)
    bm.free()
    return {"status": "ok", "restored_to": obj.name}

# =====================================================================================
# Macros parametrizadas (sobre una sola malla)
# =====================================================================================

def cmd_mesh_normals_recalc(object_name, ensure_outside=True):
    """Recalcula las normales de las caras y, si ensure_outside=True,
       invierte las que apuntan hacia el centro de masa (heurística 'outside')."""
    obj = _obj(object_name)
    if obj is None:
        return {"status":"error","message":"objeto no encontrado"}
    bm = _bm_from_object(obj)

    # 1) recálculo consistente
    try:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    except Exception:
        bm.normal_update()

    flipped = 0
    if ensure_outside:
        # Centro de masa
        vs = [v.co for v in bm.verts]
        if vs:
            cen = Vector((0,0,0))
            for v in vs: cen += v
            cen /= float(len(vs))
            # Invierte las que miran hacia dentro
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
                    # fallback manual
                    for f in to_flip:
                        f.normal_flip()

    _bm_to_object(obj, bm, recalc_normals=True)
    bm.free()
    return {"status":"ok","flipped":flipped}



def cmd_macro_nose(object_name, y_min=0.85, push_y=0.18, sharpen=0.35):
    """Macro: extruye la nariz hacia +Y y afila en X un porcentaje (sharpen)."""
    sel = cmd_select_faces_by_range(object_name, [{"axis": "y", "min": float(y_min)}])
    sid = sel.get("selection_id", 0)
    cmd_edit_extrude_selection(object_name, sid,
                               translate=(0, float(push_y), 0),
                               scale_about_center=(1.0 - float(sharpen), 1, 1),
                               inset=0.0)
    return {"status": "ok", "selection_id": sid}

def cmd_macro_pods(object_name, y0=0.15, y1=0.65, x_min=0.30, push_x=0.18, squash_z=0.12):
    """Macro: crea pods laterales en la banda media extruyendo en +X y aplastando levemente en Z."""
    sel = cmd_select_faces_by_range(object_name, [
        {"axis": "y", "min": float(y0), "max": float(y1)},
        {"axis": "x", "min": float(x_min)}
    ])
    sid = sel.get("selection_id", 0)
    cmd_edit_extrude_selection(object_name, sid,
                               translate=(float(push_x), 0, 0),
                               scale_about_center=(1, 1, 1.0 - float(squash_z)))
    return {"status": "ok", "selection_id": sid}

def cmd_macro_tail(object_name, y_max=-0.80, pull_y=0.16, inset=0.02):
    """Macro: extruye la cola hacia -Y y realiza un inset para sugerir la tobera."""
    sel = cmd_select_faces_by_range(object_name, [{"axis": "y", "max": float(y_max)}])
    sid = sel.get("selection_id", 0)
    cmd_edit_extrude_selection(object_name, sid,
                               translate=(0, -float(pull_y), 0),
                               inset=float(inset))
    return {"status": "ok", "selection_id": sid}

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

            try:
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
                elif cmd == "similarity.iou_top":
                    ack = cmd_similarity_iou_top(
                        object_name=p.get("object", ""),
                        image_path=p.get("image_path", ""),
                        res=int(p.get("res", 256)),
                        margin=float(p.get("margin", 0.05)),
                        threshold=float(p.get("threshold", 0.5))
                    )
                # --- similitud perfil y combinado ---
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

                # --- merge & stitch ---
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

                # --- normales ---
                elif cmd == "mesh.normals_recalc":
                    ack = cmd_mesh_normals_recalc(
                        object_name=p.get("object",""),
                        ensure_outside=bool(p.get("ensure_outside",True))
                    )

                # === comandos utilitarios existentes ===
                elif cmd == "export_fbx":
                    ack = {"status": "ok", "path": export_fbx(**p)}
                elif cmd == "execute_python":
                    stdout, stderr = execute_python(p.get("code", ""))
                    ack = {"status": "ok", "stdout": stdout, "stderr": stderr}
                elif cmd == "execute_python_file":
                    stdout, stderr = execute_python_file(p.get("path", ""))
                    ack = {"status": "ok", "stdout": stdout, "stderr": stderr}
                elif cmd == "identify":
                    ack = {
                        "status": "ok",
                        "module_file": __file__,
                        "websockets_version": getattr(websockets, "__version__", "unknown"),
                        "blender_version": getattr(bpy.app, "version", None),
                    }
                else:
                    ack = {"status": "ok", "echo": data}

            except Exception as exc:
                print("[DEBUG] Error procesando '{0}': {1}".format(cmd, exc))
                traceback.print_exc()
                ack = {"status": "error", "message": str(exc)}

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
