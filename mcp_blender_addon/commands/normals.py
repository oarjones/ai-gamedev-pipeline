from __future__ import annotations

from typing import Any, Dict

try:
    import bpy  # type: ignore
    import bmesh  # type: ignore
except Exception:  # pragma: no cover
    bpy = None  # type: ignore

from ..server.registry import command, tool
from ..server.context import SessionContext
from ..server.validation import get_str, ParamError


@command("normals.recalculate_selected")
@tool
def recalc_selected(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    """Recalcula normales para todos los objetos MESH seleccionados.

    Parámetros: {}
    Devuelve: { updated: int }  # número de objetos actualizados
    """
    if bpy is None:
        return {"updated": 0}

    def _impl():
        count = 0
        for obj in bpy.context.selected_objects:
            if obj.type == "MESH":
                me = obj.data
                bm = bmesh.new()
                try:
                    bm.from_mesh(me)
                    bm.normal_update()
                    bm.to_mesh(me)
                    me.update()
                    count += 1
                finally:
                    bm.free()
        return count

    updated = ctx.run_main(_impl)
    return {"updated": int(updated)}


@command("normals.recalc")
@tool
def recalc_normals(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    """Recalculate normals outward or inward.

    Params: { object: str, outside?: bool=true }
    Returns: { object: str, outside: bool, faces: int }
    """
    if bpy is None:
        raise RuntimeError("Blender API not available")

    try:
        obj_name = get_str(params, "object", required=True)
        outside = bool(params.get("outside", True))
    except ParamError as e:
        raise ValueError(str(e))

    obj = bpy.data.objects.get(obj_name)
    if obj is None or obj.type != "MESH":
        raise ValueError(f"object not found or not a mesh: {obj_name}")

    # Perform the recalculation directly.  The executor schedules this
    # command on the main thread when necessary, so we avoid calling
    # run_main here.
    ctx.ensure_object_mode()
    me = obj.data
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        # Recalculate face/vertex normals on BMesh
        bm.normal_update()
        # Flip normals for inward option
        if not outside:
            bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
        bm.to_mesh(me)
        me.update()
    finally:
        bm.free()
    return {"object": obj.name, "outside": bool(outside), "faces": len(me.polygons)}
