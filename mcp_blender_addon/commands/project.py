from __future__ import annotations

from typing import Any, Dict

try:
    import bpy  # type: ignore
    from mathutils import Vector  # type: ignore
except Exception:  # pragma: no cover
    bpy = None  # type: ignore
    Vector = None  # type: ignore

from ..server.registry import command, tool
from ..server.context import SessionContext
from ..server.logging import get_logger
from ..helpers import project as _proj


log = get_logger(__name__)


def _get_object(name: str):
    if bpy is None:
        raise RuntimeError("Blender API not available")
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ValueError(f"object not found: {name}")
    return obj


@command("project.to_blueprint_plane")
@command("helpers.project.to_blueprint_plane")
@tool
def to_blueprint_plane_cmd(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    """Project a world-space point to a blueprint plane (Empty Image) and return pixel coordinates.

    Params:
      - point: [x,y,z] world-space
      - view: "front|left|top" (string; orientation is taken from empty's transform)
      - empty: empty object name (the reference blueprint Empty)

    Returns: { u: float, v: float }
    """
    if bpy is None:
        raise RuntimeError("Blender API not available")
    try:
        pt = params.get("point")
        if not isinstance(pt, (list, tuple)) or len(pt) != 3:
            raise ValueError("point must be [x,y,z]")
        view = str(params.get("view", "front"))
        empty_name = str(params.get("empty", ""))
        empty = _get_object(empty_name)
        u, v = _proj.to_blueprint_plane(Vector((float(pt[0]), float(pt[1]), float(pt[2]))), view, empty)
        return {"u": float(u), "v": float(v)}
    except Exception as e:  # noqa: BLE001
        raise e


@command("project.from_blueprint_plane")
@command("helpers.project.from_blueprint_plane")
@tool
def from_blueprint_plane_cmd(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    """Map blueprint pixel coordinates (u,v) on an Empty Image back to a world-space point on the plane.

    Params:
      - u: float (pixel u or normalized if image is missing)
      - v: float (pixel v or normalized if image is missing)
      - view: "front|left|top"
      - empty: empty object name

    Returns: { point: [x,y,z] }
    """
    if bpy is None:
        raise RuntimeError("Blender API not available")
    try:
        u = float(params.get("u", 0.0))
        v = float(params.get("v", 0.0))
        view = str(params.get("view", "front"))
        empty_name = str(params.get("empty", ""))
        empty = _get_object(empty_name)
        world = _proj.from_blueprint_plane(u, v, view, empty)
        return {"point": [float(world.x), float(world.y), float(world.z)]}
    except Exception as e:  # noqa: BLE001
        raise e

