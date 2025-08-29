from __future__ import annotations

from typing import Any, Dict

try:
    import bpy  # type: ignore
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
