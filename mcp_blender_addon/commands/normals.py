from __future__ import annotations

from typing import Any, Dict

try:
    import bpy  # type: ignore
    import bmesh  # type: ignore
except Exception:  # pragma: no cover
    bpy = None  # type: ignore

from ..server.registry import command, tool
from ..server.context import SessionContext


@command("normals.recalculate_selected")
@tool
def recalc_selected(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    if bpy is None:
        return {"updated": 0}

    def _impl():
        count = 0
        for obj in bpy.context.selected_objects:
            if obj.type == "MESH":
                mesh = obj.data
                mesh.calc_normals()
                count += 1
        return count

    updated = ctx.run_main(_impl)
    return {"updated": int(updated)}


@command("normals.recalc")
@tool
def recalc_normals(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    if bpy is None:
        raise RuntimeError("Blender API not available")

    obj_name = params.get("object")
    outside = bool(params.get("outside", True))
    if not isinstance(obj_name, str):
        raise ValueError("params must include 'object': str")

    obj = bpy.data.objects.get(obj_name)
    if obj is None or obj.type != "MESH":
        raise ValueError(f"object not found or not a mesh: {obj_name}")

    def _impl():
        ctx.ensure_object_mode()
        me = obj.data
        me.calc_normals()
        if not outside:
            bm = bmesh.new()
            try:
                bm.from_mesh(me)
                bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
                bm.to_mesh(me)
                me.update()
            finally:
                bm.free()
        return {"object": obj.name, "outside": bool(outside), "faces": len(me.polygons)}

    return ctx.run_main(_impl)
