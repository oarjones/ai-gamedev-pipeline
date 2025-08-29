from __future__ import annotations

from typing import Any, Dict

try:
    import bpy  # type: ignore
except Exception:  # pragma: no cover
    bpy = None  # type: ignore

from ..server.registry import command, tool
from ..server.context import SessionContext


@command("modeling.echo")
@tool
def echo(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    return {"echo": params}


@command("modeling.get_version")
@tool
def get_version(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    if bpy is None:
        return {"blender": None}
    return {"blender": list(getattr(bpy.app, "version", (0, 0, 0)))}
