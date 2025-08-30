from __future__ import annotations

from typing import Any, Dict

try:
    import bpy  # type: ignore
except Exception:  # pragma: no cover
    bpy = None  # type: ignore

from ..server.registry import command, tool
from ..server.context import SessionContext
from ..server.validation import get_str, get_list_int, get_float, get_int, ParamError


@command("topology.count_mesh_objects")
@tool
def count_mesh_objects(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    if bpy is None:
        return {"count": 0}

    def _impl():
        return sum(1 for o in bpy.data.objects if o.type == "MESH")

    count = ctx.run_main(_impl)
    return {"count": int(count)}


@command("topology.ensure_object_mode")
@tool
def ensure_object_mode(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    if bpy is None:
        return {"mode": "NONE"}

    def _impl():
        return ctx.ensure_object_mode()

    mode = ctx.run_main(_impl)
    return {"mode": str(mode)}


@command("topology.touch_active")
@tool
def touch_active(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    if bpy is None:
        return {"touched": False}

    def _impl():
        obj = ctx.active_object()
        if obj is None or obj.type != "MESH":
            return False
        ctx.ensure_object_mode()
        bm = ctx.bm_from_object(obj)
        try:
            # No-op change; simply writes back ensuring paths are safe
            pass
        finally:
            ctx.bm_to_object(obj, bm)
        return True

    touched = ctx.run_main(_impl)
    return {"touched": bool(touched)}


@command("topology.bevel_edges")
@tool
def bevel_edges(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    """Bevel selected edges using bmesh.ops.bevel.

    Params: { object: str, edge_indices: list[int], offset: float, segments?: int=2, clamp?: bool=true }
    Returns: { created_edges: int, created_faces: int }
    """
    if bpy is None:
        raise RuntimeError("Blender API not available")

    try:
        import bmesh  # type: ignore
    except Exception as e:
        raise RuntimeError(f"bmesh unavailable: {e}")

    try:
        obj_name = get_str(params, "object", required=True)
        edge_indices = get_list_int(params, "edge_indices", required=True)
        offset = get_float(params, "offset", default=0.0, nonnegative=True)
        segments = get_int(params, "segments", default=2, min_value=1)
        clamp = bool(params.get("clamp", True))
    except ParamError as e:
        raise ValueError(str(e))

    obj = bpy.data.objects.get(obj_name)
    if obj is None or obj.type != "MESH":
        raise ValueError(f"object not found or not a mesh: {obj_name}")

    # Execute the bevel directly.  The executor schedules this handler on
    # Blender's main thread when necessary, so we avoid calling
    # `ctx.run_main` here to prevent threading errors on Blender 4.5.
    ctx.ensure_object_mode()
    bm = ctx.bm_from_object(obj)
    try:
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
        ecount_before = len(bm.edges)
        fcount_before = len(bm.faces)
        sel_edges = []
        max_e = ecount_before - 1
        for i in edge_indices:
            if i < 0 or i > max_e:
                raise IndexError(f"edge index out of range: {i}")
            sel_edges.append(bm.edges[i])
        if not sel_edges or offset == 0.0:
            created_e = 0
            created_f = 0
        else:
            bmesh.ops.bevel(
                bm,
                geom=sel_edges,
                offset=offset,
                segments=max(1, int(segments)),
                clamp_overlap=bool(clamp),
                affect='EDGES',
            )
            bm.normal_update()
            ecount_after = len(bm.edges)
            fcount_after = len(bm.faces)
            created_e = max(0, ecount_after - ecount_before)
            created_f = max(0, fcount_after - fcount_before)
    finally:
        ctx.bm_to_object(obj, bm)
        ctx.ensure_object_mode()
    return {"created_edges": int(created_e), "created_faces": int(created_f)}


@command("topology.merge_by_distance")
@tool
def merge_by_distance(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    """Remove doubles (merge by distance) across all verts.

    Params: { object: str, distance?: float=0.0001 }
    Returns: { removed_verts: int }
    """
    if bpy is None:
        raise RuntimeError("Blender API not available")

    try:
        import bmesh  # type: ignore
    except Exception as e:
        raise RuntimeError(f"bmesh unavailable: {e}")

    try:
        obj_name = get_str(params, "object", required=True)
        dist = get_float(params, "distance", default=0.0001, nonnegative=True)
    except ParamError as e:
        raise ValueError(str(e))

    obj = bpy.data.objects.get(obj_name)
    if obj is None or obj.type != "MESH":
        raise ValueError(f"object not found or not a mesh: {obj_name}")

    # Merge vertices directly without calling run_main.  The executor handles
    # scheduling on the main thread.
    ctx.ensure_object_mode()
    bm = ctx.bm_from_object(obj)
    try:
        v_before = len(bm.verts)
        bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=dist)
        v_after = len(bm.verts)
        bm.normal_update()
        removed = max(0, v_before - v_after)
    finally:
        ctx.bm_to_object(obj, bm)
        ctx.ensure_object_mode()
    return {"removed_verts": int(removed)}
