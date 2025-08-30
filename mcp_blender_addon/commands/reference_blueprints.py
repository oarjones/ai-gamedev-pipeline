from __future__ import annotations

import json
import math
import os
from typing import Any, Dict, Optional

try:
    import bpy  # type: ignore
except Exception:  # pragma: no cover
    bpy = None  # type: ignore

from ..server.registry import command, tool
from ..server.context import SessionContext
from ..server.logging import get_logger


log = get_logger(__name__)


SCENE_PROP = "mw_ref_blueprints"


def _scene_store_get() -> Dict[str, Any]:
    if bpy is None:
        return {}
    raw = bpy.context.scene.get(SCENE_PROP)
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _scene_store_set(data: Dict[str, Any]) -> None:
    if bpy is None:
        return
    try:
        bpy.context.scene[SCENE_PROP] = json.dumps(data, separators=(",", ":"))
    except Exception:
        pass


def _image_from_path(path: str):
    if bpy is None:
        raise RuntimeError("Blender API not available")
    if not isinstance(path, str) or not path:
        raise ValueError("image path required")
    # Sanitize: prefer absolute path to avoid surprising relative resolution
    p = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(p):
        raise ValueError(f"image not found: {p}")
    try:
        img = bpy.data.images.load(p, check_existing=True)
        return img
    except Exception as e:
        raise ValueError(f"failed to load image: {e}")


def _unique_name(base: str) -> str:
    if bpy is None:
        return base
    if base not in bpy.data.objects:
        return base
    i = 1
    while True:
        cand = f"{base}.{i:03d}"
        if cand not in bpy.data.objects:
            return cand
        i += 1


def _create_image_empty(name: str, img, size: float, opacity: float, rot_xyz: tuple[float, float, float], lock: bool):
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = 'IMAGE'
    obj.empty_display_size = float(max(1e-4, size))
    # Assign image datablock
    try:
        obj.data = img  # type: ignore[assignment]
    except Exception:
        pass
    # Center pivot to image center
    try:
        obj.empty_image_offset = (0.5, 0.5)  # type: ignore[attr-defined]
    except Exception:
        pass
    # Depth in front of geometry
    try:
        obj.empty_image_depth = 'FRONT'  # type: ignore[attr-defined]
    except Exception:
        pass
    # Show in front of all (helps visibility)
    try:
        obj.show_in_front = True  # type: ignore[attr-defined]
    except Exception:
        pass
    # Visibility: only in orthographic view if supported
    try:
        obj.empty_image_show_orthographic = True  # type: ignore[attr-defined]
        obj.empty_image_show_perspective = False  # type: ignore[attr-defined]
    except Exception:
        pass
    # Opacity
    try:
        obj.empty_image_alpha = float(max(0.0, min(1.0, opacity)))  # type: ignore[attr-defined]
    except Exception:
        pass

    obj.rotation_euler = rot_xyz  # type: ignore[assignment]
    obj.location = (0.0, 0.0, 0.0)  # type: ignore[assignment]

    if lock:
        obj.lock_location = (True, True, True)
        obj.lock_rotation = (True, True, True)
        obj.lock_scale = (True, True, True)

    # Link to collection
    col = bpy.context.collection or bpy.context.scene.collection
    col.objects.link(obj)
    return obj


@command("ref.blueprints_setup")
@tool
def blueprints_setup(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    if bpy is None:
        raise RuntimeError("Blender API not available")

    front = str(params.get("front", ""))
    left = str(params.get("left", ""))
    top = str(params.get("top", ""))
    size = float(params.get("size", 1.0))
    opacity = float(params.get("opacity", 0.4))
    lock = bool(params.get("lock", True))

    if not front or not left or not top:
        raise ValueError("front, left, top image paths are required")
    size = max(0.01, min(10_000.0, size))
    opacity = max(0.0, min(1.0, opacity))

    ctx.ensure_object_mode()

    img_front = _image_from_path(front)
    img_left = _image_from_path(left)
    img_top = _image_from_path(top)

    # Create empties with appropriate orientations
    front_rot = (math.radians(90.0), 0.0, 0.0)  # normal -> +Y
    left_rot = (0.0, math.radians(-90.0), 0.0)  # normal -> +X
    top_rot = (0.0, 0.0, 0.0)  # normal -> +Z

    o_front = _create_image_empty(_unique_name("REF_FRONT"), img_front, size, opacity, front_rot, lock)
    o_left = _create_image_empty(_unique_name("REF_LEFT"), img_left, size, opacity, left_rot, lock)
    o_top = _create_image_empty(_unique_name("REF_TOP"), img_top, size, opacity, top_rot, lock)

    # Persist ids in scene for robust updates/removal
    data = {
        "front": o_front.name,
        "left": o_left.name,
        "top": o_top.name,
    }
    _scene_store_set(data)

    log.info("blueprints_setup size=%.3f opacity=%.2f lock=%s ids=%s", size, opacity, lock, data)
    return {"ids": data}


def _get_blueprint_object(which: str) -> Optional[Any]:
    if bpy is None:
        return None
    data = _scene_store_get()
    key = which.lower()
    if key not in {"front", "left", "top"}:
        raise ValueError("which must be one of front|left|top")
    name = data.get(key)
    if not name:
        return None
    return bpy.data.objects.get(name)


@command("ref.blueprints_update")
@tool
def blueprints_update(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    if bpy is None:
        raise RuntimeError("Blender API not available")

    which = str(params.get("which", "")).lower()
    if which not in {"front", "left", "top"}:
        raise ValueError("which must be one of front|left|top")

    img_path = params.get("image")
    opacity = params.get("opacity")
    visible = params.get("visible")

    obj = _get_blueprint_object(which)
    if obj is None:
        raise ValueError(f"blueprint '{which}' not found; run ref.blueprints_setup first")

    if img_path:
        img = _image_from_path(str(img_path))
        try:
            obj.data = img  # type: ignore[assignment]
        except Exception:
            pass

    if opacity is not None:
        try:
            obj.empty_image_alpha = float(max(0.0, min(1.0, float(opacity))))  # type: ignore[attr-defined]
        except Exception:
            pass

    if visible is not None:
        vis = bool(visible)
        try:
            obj.hide_viewport = not vis
        except Exception:
            pass

    log.info("blueprints_update which=%s image=%s opacity=%s visible=%s", which, bool(img_path), opacity, visible)
    return {"updated": which}


@command("ref.blueprints_remove")
@tool
def blueprints_remove(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    if bpy is None:
        raise RuntimeError("Blender API not available")

    data = _scene_store_get()
    removed = []
    for key in ("front", "left", "top"):
        name = data.get(key)
        if not name:
            continue
        obj = bpy.data.objects.get(name)
        if obj is not None:
            try:
                # Unlink from all collections first
                for coll in list(obj.users_collection):
                    try:
                        coll.objects.unlink(obj)
                    except Exception:
                        pass
                bpy.data.objects.remove(obj, do_unlink=True)
                removed.append(name)
            except Exception:
                pass
    # Clear scene store
    _scene_store_set({})
    log.info("blueprints_remove removed=%s", removed)
    return {"removed": removed}

