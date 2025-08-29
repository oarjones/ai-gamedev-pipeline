from __future__ import annotations

from typing import Any, Dict

try:
    import bpy  # type: ignore
except Exception:  # pragma: no cover
    bpy = None  # type: ignore

from ..server.registry import Registry
from ..server.executor import Executor


def register(registry: Registry, executor: Executor) -> None:
    registry.register("topology.count_mesh_objects", lambda params: _count_mesh_objects(executor))


def _count_mesh_objects(executor: Executor) -> Dict[str, Any]:
    if bpy is None:
        return {"count": 0}

    def _impl():
        return sum(1 for o in bpy.data.objects if o.type == "MESH")

    count = executor.submit(_impl)
    return {"count": int(count)}

