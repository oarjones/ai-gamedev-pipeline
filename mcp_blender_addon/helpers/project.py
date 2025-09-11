from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

try:
    import bpy  # type: ignore
    from mathutils import Vector, Matrix  # type: ignore
except Exception:  # pragma: no cover
    bpy = None  # type: ignore
    Vector = None  # type: ignore
    Matrix = None  # type: ignore

from ..server.logging import get_logger


log = get_logger(__name__)


def _image_size(empty_obj) -> Tuple[int, int]:
    img = getattr(empty_obj, "data", None)
    try:
        w = int(img.size[0]) if img is not None else 0
        h = int(img.size[1]) if img is not None else 0
    except Exception:
        w, h = 0, 0
    return max(0, w), max(0, h)


def _plane_dims_and_offset(empty_obj) -> Tuple[float, float, float, float]:
    """Return (plane_w, plane_h, ox, oy) where (ox,oy) are normalized offsets.

    - plane is the Empty Image local XY plane
    - plane_w = empty_display_size
    - plane_h = empty_display_size * (image_h / image_w) if image present, else same as width
    - offset defaults to (0.5, 0.5) if attribute is missing
    """
    size = float(getattr(empty_obj, "empty_display_size", 1.0))
    img_w, img_h = _image_size(empty_obj)
    if img_w > 0 and img_h > 0:
        aspect = img_h / img_w
        plane_w, plane_h = size, size * aspect
    else:
        plane_w = plane_h = size
    try:
        ox, oy = getattr(empty_obj, "empty_image_offset", (0.5, 0.5))  # type: ignore[attr-defined]
        ox = float(ox)
        oy = float(oy)
    except Exception:
        ox, oy = 0.5, 0.5
    return plane_w, plane_h, ox, oy


def to_blueprint_plane(world_co: "Vector", view: str, empty_obj) -> Tuple[float, float]:
    """Project a world-space point onto the blueprint plane and return pixel (u,v).

    Conventions by view (Empty orientation should match):
      - front: image plane faces +Y; local X maps to world +X, local Y maps to world -Z
      - left: plane faces +X; local X~world +Y, local Y~world +Z
      - top: plane faces +Z; local X~world +X, local Y~world +Y
    The function relies on empty_obj.matrix_world for exact mapping rather than hardcoded axes.
    """
    if bpy is None or Vector is None:
        raise RuntimeError("Blender API not available")
    if not hasattr(world_co, "x"):
        world_co = Vector(world_co)  # type: ignore[arg-type]

    M_inv = empty_obj.matrix_world.inverted()
    p_local = M_inv @ world_co
    plane_w, plane_h, ox, oy = _plane_dims_and_offset(empty_obj)
    u_norm = p_local.x / max(1e-9, plane_w) + ox
    v_norm = p_local.y / max(1e-9, plane_h) + oy
    img_w, img_h = _image_size(empty_obj)
    if img_w <= 0 or img_h <= 0:
        # Return normalized if no image
        return float(u_norm), float(v_norm)
    u_px = u_norm * img_w
    v_px = v_norm * img_h
    return float(u_px), float(v_px)


def from_blueprint_plane(u: float, v: float, view: str, empty_obj) -> "Vector":
    """Map pixel (u,v) on the blueprint image back to a world-space point on the plane (z=0 in empty local).

    Conventions follow to_blueprint_plane.
    """
    if bpy is None or Vector is None or Matrix is None:
        raise RuntimeError("Blender API not available")
    img_w, img_h = _image_size(empty_obj)
    plane_w, plane_h, ox, oy = _plane_dims_and_offset(empty_obj)
    if img_w > 0 and img_h > 0:
        u_norm = float(u) / max(1e-9, img_w)
        v_norm = float(v) / max(1e-9, img_h)
    else:
        u_norm = float(u)
        v_norm = float(v)
    x = (u_norm - ox) * plane_w
    y = (v_norm - oy) * plane_h
    p_local = Vector((x, y, 0.0))
    world = empty_obj.matrix_world @ p_local
    return world


def image_bbox_from_alpha(image, threshold: float) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    """Compute axis-aligned bbox in pixel space for alpha >= threshold.

    Returns ((min_u, min_v), (max_u, max_v)); if image has no alpha region above threshold,
    raises ValueError.
    """
    if bpy is None:
        raise RuntimeError("Blender API not available")
    try:
        w = int(image.size[0])
        h = int(image.size[1])
    except Exception:
        raise ValueError("invalid image")
    if w <= 0 or h <= 0:
        raise ValueError("invalid image dimensions")
    try:
        pix = image.pixels
    except Exception:
        raise ValueError("image has no pixel buffer")
    thr = float(max(0.0, min(1.0, threshold)))
    umin = float("inf")
    vmin = float("inf")
    umax = float("-inf")
    vmax = float("-inf")
    found = False
    # iterate alpha channel only (stride 4)
    idx = 3
    j = 0
    total = w * h
    for j in range(h):
        base = j * w * 4
        for i in range(w):
            a = pix[base + i * 4 + 3]
            if a >= thr:
                u = float(i)
                v = float(j)
                if u < umin:
                    umin = u
                if v < vmin:
                    vmin = v
                if u > umax:
                    umax = u
                if v > vmax:
                    vmax = v
                found = True
    if not found:
        raise ValueError("no pixels above threshold")
    return (umin, vmin), (umax, vmax)


def project_mesh_bbox(obj_or_name: Any, view: str, empty_obj) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    """Project a mesh's vertices to the blueprint plane and compute bbox in pixels.

    Returns ((min_u,min_v),(max_u,max_v)).
    """
    if bpy is None:
        raise RuntimeError("Blender API not available")
    obj = obj_or_name
    if not hasattr(obj_or_name, "type"):
        obj = bpy.data.objects.get(str(obj_or_name))
    if obj is None or getattr(obj, "type", None) != "MESH":
        raise ValueError("object must be a mesh or mesh name")
    img_w, img_h = _image_size(empty_obj)
    plane_w, plane_h, ox, oy = _plane_dims_and_offset(empty_obj)
    M_inv = empty_obj.matrix_world.inverted()
    umin = float("inf")
    vmin = float("inf")
    umax = float("-inf")
    vmax = float("-inf")
    for v in obj.data.vertices:
        p_local = M_inv @ (obj.matrix_world @ v.co)
        u_norm = p_local.x / max(1e-9, plane_w) + ox
        v_norm = p_local.y / max(1e-9, plane_h) + oy
        u = u_norm * img_w if img_w > 0 else u_norm
        vv = v_norm * img_h if img_h > 0 else v_norm
        if u < umin:
            umin = u
        if vv < vmin:
            vmin = vv
        if u > umax:
            umax = u
        if vv > vmax:
            vmax = vv
    return (umin, vmin), (umax, vmax)

