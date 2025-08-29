from __future__ import annotations

from typing import Any, Dict

try:
    import bpy  # type: ignore
except Exception:  # pragma: no cover
    bpy = None  # type: ignore

from ..server.registry import Registry
from ..server.executor import Executor


def register(registry: Registry, executor: Executor) -> None:
    registry.register("normals.recalculate_selected", lambda params: _recalc_selected(executor))


def _recalc_selected(executor: Executor) -> Dict[str, Any]:
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

    updated = executor.submit(_impl)
    return {"updated": int(updated)}

