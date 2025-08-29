from __future__ import annotations

from typing import Any, Dict

try:
    import bpy  # type: ignore
except Exception:  # pragma: no cover
    bpy = None  # type: ignore

from ..server.registry import command, tool
from ..server.context import SessionContext


@command("topology.count_mesh_objects")
@tool
def count_mesh_objects(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    if bpy is None:
        return {"count": 0}

    def _impl():
        return sum(1 for o in bpy.data.objects if o.type == "MESH")

    count = ctx.run_main(_impl)
    return {"count": int(count)}
