from __future__ import annotations

import random
from typing import Any, Dict, List, Tuple

try:
    import bpy  # type: ignore
    import bmesh  # type: ignore
except Exception:  # pragma: no cover
    bpy = None  # type: ignore
    bmesh = None  # type: ignore

from ..server.registry import command, tool
from ..server.context import SessionContext
from ..server.logging import get_logger


log = get_logger(__name__)


def _unique_name(existing, base: str) -> str:
    if base not in existing:
        return base
    i = 1
    while True:
        cand = f"{base}.{i:03d}"
        if cand not in existing:
            return cand
        i += 1


def _create_box_object(name: str, size_x: float, size_y: float, size_z: float):
    bm = bmesh.new()
    try:
        bmesh.ops.create_cube(bm, size=1.0)
        sx = max(1e-6, size_x * 0.5)
        sy = max(1e-6, size_y * 0.5)
        sz = max(1e-6, size_z * 0.5)
        bmesh.ops.scale(bm, vec=(sx, sy, sz), verts=bm.verts)
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        me.update()
    finally:
        bm.free()
    obj = bpy.data.objects.new(name, me)
    return obj


def _apply_all(obj) -> None:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    obj_eval = obj.evaluated_get(depsgraph)
    mesh_eval = obj_eval.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
    new_me = mesh_eval.copy()
    obj_eval.to_mesh_clear()
    old_me = obj.data
    obj.data = new_me
    try:
        if old_me.users == 0:
            bpy.data.meshes.remove(old_me)
    except Exception:
        pass
    try:
        new_me.update()
    except Exception:
        pass
    try:
        obj.modifiers.clear()
    except Exception:
        for m in list(obj.modifiers):
            try:
                obj.modifiers.remove(m)
            except Exception:
                pass


@command("proc.building")
@tool
def building(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    """Procedurally generate a simple building shell with window cutouts.

    Strategy: base parallelepiped -> Solidify (walls) -> Boolean difference with window cutters.
    Window placement is pseudo-random but seeded and reproducible.
    """
    if bpy is None or bmesh is None:
        raise RuntimeError("Blender API not available")

    floors = int(params.get("floors", 5))
    bays = int(params.get("bays", 4))
    bay_width = float(params.get("bay_width", 3.0))
    floor_height = float(params.get("floor_height", 3.0))
    depth = float(params.get("depth", 6.0))
    wall_thickness = float(params.get("wall_thickness", 0.2))
    window_w = float(params.get("window_w", 1.2))
    window_h = float(params.get("window_h", 1.2))
    seed = int(params.get("seed", 0))

    # Clamp & validate
    floors = max(1, min(200, floors))
    bays = max(1, min(200, bays))
    bay_width = max(0.5, min(100.0, bay_width))
    floor_height = max(1.8, min(100.0, floor_height))
    depth = max(1.0, min(200.0, depth))
    wall_thickness = max(0.02, min(min(bay_width, floor_height) * 0.45, wall_thickness))
    window_w = max(0.2, min(bay_width - 2 * 0.1, window_w))
    window_h = max(0.2, min(floor_height - 2 * 0.1, window_h))

    total_width = bay_width * bays
    total_height = floor_height * floors

    ctx.ensure_object_mode()

    # Create base box
    base_name = _unique_name(bpy.data.objects, f"Building_{seed}_{floors}x{bays}")
    obj = _create_box_object(base_name, total_width, depth, total_height)
    collection = bpy.context.collection or bpy.context.scene.collection
    collection.objects.link(obj)

    # Add Solidify (inward) for wall thickness
    solid = obj.modifiers.new(name="Solidify", type='SOLIDIFY')
    try:
        solid.thickness = float(wall_thickness)  # type: ignore[attr-defined]
    except Exception:
        pass
    try:
        solid.offset = -1.0  # thicken inwards  # type: ignore[attr-defined]
    except Exception:
        pass

    # Create window cutters collection
    win_col_name = _unique_name(bpy.data.collections, f"BuildingWindows_{seed}_{floors}x{bays}")
    win_col = bpy.data.collections.new(win_col_name)
    bpy.context.scene.collection.children.link(win_col)

    rng = random.Random(seed)
    include_prob = 0.85

    # Helper to create a window cutter box and link to collection
    def make_window(name: str, size: Tuple[float, float, float], loc: Tuple[float, float, float]):
        wobj = _create_box_object(name, size[0], size[1], size[2])
        wobj.location = loc  # type: ignore[assignment]
        win_col.objects.link(wobj)
        return wobj

    # Margins inside a bay and floor
    margin_x = max(0.05, min(0.5, 0.1 * bay_width))
    margin_z = max(0.05, min(0.5, 0.1 * floor_height))
    # Clamp window sizes to cell after margins
    cell_w = total_width / bays
    cell_h = floor_height
    max_ww = max(0.1, cell_w - 2 * margin_x)
    max_wh = max(0.1, cell_h - 2 * margin_z)
    ww = min(window_w, max_ww)
    wh = min(window_h, max_wh)

    # Depth window extrusion slightly larger than wall to ensure clean boolean
    cut_depth = wall_thickness * 2.0

    # Front/back facades (along X), place windows across bays and floors
    half_w = total_width * 0.5
    half_d = depth * 0.5
    half_h = total_height * 0.5

    created_cutters: List[str] = []

    for side, ysign in (("front", 1.0), ("back", -1.0)):
        y_center = ysign * (half_d - wall_thickness * 0.5)
        for f in range(floors):
            zc = -half_h + (f + 0.5) * floor_height
            for b in range(bays):
                if rng.random() > include_prob:
                    continue
                xc = -half_w + (b + 0.5) * cell_w
                wname = _unique_name(bpy.data.objects, f"Win_{side}_{f}_{b}_{seed}")
                w = make_window(wname, (ww, cut_depth, wh), (xc, y_center, zc))
                created_cutters.append(w.name)

    # Left/right facades (along Y): estimate columns by depth/bay_width
    depth_bays = max(1, min(bays, int(round(depth / max(0.5, bay_width)))))
    cell_d = depth / depth_bays
    max_ww_lr = max(0.1, cell_d - 2 * margin_x)
    ww_lr = min(window_w, max_ww_lr)

    for side, xsign in (("right", 1.0), ("left", -1.0)):
        x_center = xsign * (half_w - wall_thickness * 0.5)
        for f in range(floors):
            zc = -half_h + (f + 0.5) * floor_height
            for b in range(depth_bays):
                if rng.random() > include_prob:
                    continue
                yc = -half_d + (b + 0.5) * cell_d
                wname = _unique_name(bpy.data.objects, f"Win_{side}_{f}_{b}_{seed}")
                w = make_window(wname, (cut_depth, ww_lr, wh), (x_center, yc, zc))
                created_cutters.append(w.name)

    # Add Boolean difference using the collection of cutters
    bool_mod = obj.modifiers.new(name="Windows", type='BOOLEAN')
    try:
        bool_mod.operation = 'DIFFERENCE'  # type: ignore[attr-defined]
    except Exception:
        pass
    try:
        bool_mod.collection = win_col  # type: ignore[attr-defined]
    except Exception:
        # Older versions only support single object; in that case, skip collection assignment
        pass
    try:
        bool_mod.solver = 'FAST'  # type: ignore[attr-defined]
    except Exception:
        pass

    # Apply modifiers in order (solidify then boolean)
    _apply_all(obj)

    # Clean up window cutters collection and objects to keep scene clean
    try:
        for o in list(win_col.objects):
            try:
                bpy.data.objects.remove(o, do_unlink=True)
            except Exception:
                pass
        # Unlink and remove collection
        try:
            bpy.context.scene.collection.children.unlink(win_col)
        except Exception:
            pass
        bpy.data.collections.remove(win_col)
    except Exception:
        pass

    log.info(
        "proc.building seed=%s floors=%s bays=%s size=(%.2f,%.2f,%.2f) windows=%s",
        seed,
        floors,
        bays,
        total_width,
        depth,
        total_height,
        len(created_cutters),
    )

    return {"object_name": obj.name}

