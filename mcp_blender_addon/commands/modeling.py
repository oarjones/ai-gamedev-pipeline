from __future__ import annotations

from typing import Any, Dict

try:
    import bpy  # type: ignore
except Exception:  # pragma: no cover
    bpy = None  # type: ignore

from ..server.registry import Registry
from ..server.executor import Executor


def register(registry: Registry, executor: Executor) -> None:
    registry.register("modeling.echo", _echo)
    registry.register("modeling.get_version", lambda params: _get_version())


def _echo(params: Dict[str, Any]) -> Dict[str, Any]:
    return {"echo": params}


def _get_version():
    if bpy is None:
        return {"blender": None}
    return {"blender": list(getattr(bpy.app, "version", (0, 0, 0)))}

