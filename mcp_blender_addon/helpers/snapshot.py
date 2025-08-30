from __future__ import annotations

import base64
import os
import tempfile
from dataclasses import dataclass
from typing import Any, Dict, Optional

try:
    import bpy  # type: ignore
    from mathutils import Vector, Matrix  # type: ignore
except Exception:  # pragma: no cover - outside Blender
    bpy = None  # type: ignore
    Vector = None  # type: ignore
    Matrix = None  # type: ignore

from ..server.logging import get_logger
from ..server.registry import command, tool
from ..server.context import SessionContext


log = get_logger(__name__)


VALID_VIEWS = {
    "front",
    "back",
    "left",
    "right",
    "top",
    "bottom",
    "iso",
}
VALID_SHADING = {"SOLID", "MATERIAL"}


@dataclass
class _View3DHandle:
    window: Any
    screen: Any
    area: Any
    region: Any
    space: Any
    r3d: Any


def _find_view3d() -> Optional[_View3DHandle]:
    if bpy is None:
        return None
    # Prefer current window's first VIEW_3D area
    try:
        windows = list(bpy.context.window_manager.windows)
    except Exception:
        windows = []
    if not windows:
        return None
    for win in windows:
        scr = getattr(win, "screen", None)
        if not scr:
            continue
        for area in scr.areas:
            if area.type != "VIEW_3D":
                continue
            # WINDOW region is needed for render ops
            region = None
            for reg in area.regions:
                if reg.type == "WINDOW":
                    region = reg
                    break
            if region is None:
                continue
            space = area.spaces.active
            r3d = space.region_3d if hasattr(space, "region_3d") else None
            if r3d is None:
                continue
            return _View3DHandle(window=win, screen=scr, area=area, region=region, space=space, r3d=r3d)
    return None


def _orientation_quaternion(view: str) -> Matrix:
    """Compute a rotation matrix for the requested view.

    Returns a Matrix whose quaternion can be assigned to RegionView3D.view_rotation.
    The mapping aligns the viewport forward vector and screen-up with Blender's
    conventional axes for standard views.
    """
    assert Vector is not None and Matrix is not None
    v = view.lower()

    if v == "front":
        f = Vector((0.0, -1.0, 0.0))
        up = Vector((0.0, 0.0, 1.0))
    elif v == "back":
        f = Vector((0.0, 1.0, 0.0))
        up = Vector((0.0, 0.0, 1.0))
    elif v == "right":
        f = Vector((1.0, 0.0, 0.0))
        up = Vector((0.0, 0.0, 1.0))
    elif v == "left":
        f = Vector((-1.0, 0.0, 0.0))
        up = Vector((0.0, 0.0, 1.0))
    elif v == "top":
        f = Vector((0.0, 0.0, -1.0))
        # keep screen up towards -Y so +Y points down on screen, matching Blender
        up = Vector((0.0, -1.0, 0.0))
    elif v == "bottom":
        f = Vector((0.0, 0.0, 1.0))
        up = Vector((0.0, -1.0, 0.0))
    else:  # iso 3/4: from top-right-front
        f = Vector((1.0, -1.0, -1.0)).normalized()
        up = Vector((0.0, 0.0, 1.0))

    # Build orthonormal basis: right, up, -forward as columns
    f = f.normalized()
    up = up.normalized()
    # Ensure up not colinear with forward
    if abs(f.dot(up)) > 0.999:
        up = Vector((0.0, 1.0, 0.0)) if abs(f.z) > 0.5 else Vector((0.0, 0.0, 1.0))
    right = up.cross(f).normalized()
    up_ortho = f.cross(right).normalized()
    # Compose rotation matrix (columns are basis vectors)
    m = Matrix((right, up_ortho, -f)).transposed()
    return m


def _center_view_on_active(r3d: Any) -> None:
    try:
        obj = bpy.context.view_layer.objects.active  # type: ignore[attr-defined]
    except Exception:
        obj = None
    loc = Vector((0.0, 0.0, 0.0)) if Vector is not None else (0.0, 0.0, 0.0)
    if obj is not None:
        try:
            loc = obj.matrix_world.to_translation()
        except Exception:
            try:
                loc = obj.location.copy()
            except Exception:
                pass
    try:
        r3d.view_location = loc
    except Exception:
        pass


def _validate_inputs(view: str, perspective: bool, width: int, height: int, shading: str) -> None:
    if not isinstance(view, str) or view.lower() not in VALID_VIEWS:
        raise ValueError(f"invalid view: {view}; must be one of {sorted(VALID_VIEWS)}")
    if not isinstance(perspective, bool):
        raise ValueError("perspective must be bool")
    if not isinstance(width, int) or not isinstance(height, int):
        raise ValueError("width/height must be int")
    if width < 16 or height < 16 or width > 8192 or height > 8192:
        raise ValueError("width/height out of bounds (16..8192)")
    if shading not in VALID_SHADING:
        raise ValueError(f"invalid shading: {shading}; must be one of {sorted(VALID_SHADING)}")


def capture_view(
    view: str,
    perspective: bool = False,
    width: int = 768,
    height: int = 768,
    shading: str = "SOLID",
    return_base64: bool = True,
    *,
    overlay_wireframe: bool = False,
) -> Dict[str, Any]:
    """Capture a PNG snapshot of the active 3D Viewport.

    - Orients the viewport to one of: front/back/left/right/top/bottom/iso.
    - Switches to orthographic if perspective=False; otherwise perspective.
    - Sets viewport shading to SOLID (default) or MATERIAL.
    - Centers view on active object if present, else origin.
    - Saves a unique temporary PNG at requested width/height via viewport render.

    Returns a structured dict with file path and optional base64.

    Notes (Blender 4.5):
    - Avoids bpy.ops except for the viewport snapshot (render.render with use_viewport=True).
    - Assumes execution on Blender's main thread (as per addon executor timers).
    """
    if bpy is None:
        raise RuntimeError("Blender API not available")

    _validate_inputs(view, perspective, width, height, shading)

    handle = _find_view3d()
    if handle is None:
        raise RuntimeError("No VIEW_3D area/region available for snapshot")

    win, area, region, space, r3d = handle.window, handle.area, handle.region, handle.space, handle.r3d

    # Preserve state to restore after snapshot
    prev = {
        "view_perspective": getattr(r3d, "view_perspective", "PERSP"),
        "view_rotation": getattr(r3d, "view_rotation", None).copy() if getattr(r3d, "view_rotation", None) else None,
        "view_location": getattr(r3d, "view_location", None).copy() if getattr(r3d, "view_location", None) else None,
        "shading": getattr(space.shading, "type", "SOLID"),
        "overlay_wire": getattr(space.overlay, "show_wireframes", False),
        "res_x": bpy.context.scene.render.resolution_x,
        "res_y": bpy.context.scene.render.resolution_y,
        "res_pct": bpy.context.scene.render.resolution_percentage,
        "filepath": bpy.context.scene.render.filepath,
        "file_format": bpy.context.scene.render.image_settings.file_format,
    }

    # Prepare a unique temp filepath
    tmp = tempfile.NamedTemporaryFile(prefix="viewport_", suffix=".png", delete=False)
    tmp_path = tmp.name
    tmp.close()

    created_ok = False
    size_bytes = 0
    try:
        # Configure viewport orientation and shading
        try:
            m = _orientation_quaternion(view)
            r3d.view_rotation = m.to_quaternion()
        except Exception as e:
            log.info("Failed to set view rotation, view=%s err=%s", view, e)
        try:
            r3d.view_perspective = "PERSP" if perspective else "ORTHO"
        except Exception:
            pass

        _center_view_on_active(r3d)

        # Shading and overlay
        try:
            space.shading.type = shading
        except Exception:
            pass
        try:
            space.overlay.show_wireframes = bool(overlay_wireframe)
        except Exception:
            pass

        # Scene render settings for exact output size
        scene = bpy.context.scene
        rnd = scene.render
        rnd.image_settings.file_format = "PNG"
        rnd.resolution_x = int(width)
        rnd.resolution_y = int(height)
        rnd.resolution_percentage = 100
        rnd.filepath = tmp_path

        # Context override to ensure viewport render uses this 3D View
        override = {
            "window": win,
            "screen": handle.screen,
            "area": area,
            "region": region,
            "space_data": space,
            "scene": scene,
        }

        # Perform viewport render (allowed bpy.ops usage)
        res = bpy.ops.render.render(override, write_still=True, use_viewport=True)
        if res not in {{"FINISHED"}}:
            log.info("Viewport render returned: %s", res)

        # Verify file was created
        if os.path.exists(tmp_path):
            created_ok = True
            try:
                size_bytes = os.path.getsize(tmp_path)
            except Exception:
                size_bytes = 0
        else:
            raise RuntimeError("snapshot not created")

        # Optional base64
        b64: Optional[str] = None
        if return_base64:
            with open(tmp_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")

        payload = {
            "path": tmp_path,
            "width": int(width),
            "height": int(height),
            "view": view.lower(),
            "perspective": bool(perspective),
            "shading": shading,
            "overlay_wireframe": bool(overlay_wireframe),
            "size_bytes": int(size_bytes),
        }
        if return_base64:
            payload["base64"] = b64
        return payload
    finally:
        # Restore state
        try:
            if prev["view_rotation"] is not None:
                r3d.view_rotation = prev["view_rotation"]
            if prev["view_location"] is not None:
                r3d.view_location = prev["view_location"]
            r3d.view_perspective = prev["view_perspective"]
        except Exception:
            pass
        try:
            space.shading.type = prev["shading"]
        except Exception:
            pass
        try:
            space.overlay.show_wireframes = prev["overlay_wire"]
        except Exception:
            pass
        try:
            scene = bpy.context.scene
            rnd = scene.render
            rnd.resolution_x = prev["res_x"]
            rnd.resolution_y = prev["res_y"]
            rnd.resolution_percentage = prev["res_pct"]
            rnd.filepath = prev["filepath"]
            rnd.image_settings.file_format = prev["file_format"]
        except Exception:
            pass
        if not created_ok:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass


@command("helpers.capture_view")
@tool
def capture_view_cmd(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    """Command wrapper for viewport snapshot.

    Params:
      - view: "front|back|left|right|top|bottom|iso"
      - perspective: bool (default False -> ORTHO)
      - width: int (16..8192, default 768)
      - height: int (16..8192, default 768)
      - shading: "SOLID" | "MATERIAL" (default SOLID)
      - return_base64: bool (default True)
      - overlay_wireframe: bool (default False)

    Returns: { path, width, height, view, perspective, shading, overlay_wireframe, size_bytes, base64? }
    """
    if bpy is None:
        raise RuntimeError("Blender API not available")

    # Basic param parsing with sane defaults
    try:
        view = str(params.get("view", "front")).lower()
        perspective = bool(params.get("perspective", False))
        width = int(params.get("width", 768))
        height = int(params.get("height", 768))
        shading = str(params.get("shading", "SOLID")).upper()
        return_base64 = bool(params.get("return_base64", True))
        overlay_wireframe = bool(params.get("overlay_wireframe", False))
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"invalid parameters: {e}")

    # Validate early for clearer errors
    _validate_inputs(view, perspective, width, height, shading)

    log.info(
        "snapshot request view=%s persp=%s size=%dx%d shading=%s wire=%s",
        view,
        perspective,
        width,
        height,
        shading,
        overlay_wireframe,
    )

    return capture_view(
        view=view,
        perspective=perspective,
        width=width,
        height=height,
        shading=shading,
        return_base64=return_base64,
        overlay_wireframe=overlay_wireframe,
    )

