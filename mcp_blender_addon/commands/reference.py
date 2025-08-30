from __future__ import annotations

import math
import os
from typing import Any, Dict, Optional, Tuple

try:
    import bpy  # type: ignore
    from mathutils import Vector, Matrix  # type: ignore
except Exception:  # pragma: no cover
    bpy = None  # type: ignore
    Vector = None  # type: ignore
    Matrix = None  # type: ignore

from ..server.registry import command, tool
from ..server.context import SessionContext
from ..server.logging import get_logger


log = get_logger(__name__)


SCENE_BP_KEY = "mw_ref_blueprints"  # used by reference_blueprints


def _get_mesh_object(name: str):
    if bpy is None:
        raise RuntimeError("Blender API not available")
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ValueError(f"object not found: {name}")
    if obj.type != "MESH":
        raise TypeError(f"object is not a mesh: {name}")
    return obj


def _get_blueprint_empty(view: str) -> Optional[Any]:
    if bpy is None:
        return None
    try:
        payload = bpy.context.scene.get(SCENE_BP_KEY)
    except Exception:
        payload = None
    if not payload:
        return None
    try:
        import json

        data = json.loads(payload)
    except Exception:
        return None
    name = data.get(view.lower()) if isinstance(data, dict) else None
    if not name:
        return None
    return bpy.data.objects.get(name)


def _load_image(path: str):
    p = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(p):
        raise ValueError(f"image not found: {p}")
    try:
        return bpy.data.images.load(p, check_existing=True)
    except Exception as e:
        raise ValueError(f"failed to load image: {e}")


def _silhouette_bbox_from_image(img, alpha_threshold: float) -> Tuple[Tuple[float, float, float, float], Tuple[int, int]]:
    """Compute 2D bbox (u_min, v_min, u_max, v_max) in normalized [0,1] space for opaque pixels.

    If alpha channel is uniform (no alpha), fallback to luminance threshold where ink = (1 - luminance) >= alpha_threshold.
    Returns bbox and (width,height) in pixels.
    """
    w = int(getattr(img, "size", [0, 0])[0])
    h = int(getattr(img, "size", [0, 0])[1])
    if w <= 0 or h <= 0:
        raise ValueError("invalid image dimensions")
    try:
        pixels = list(img.pixels)
    except Exception:
        # As last resort, try to reload
        pixels = list(img.pixels)
    if len(pixels) < 4 * w * h:
        raise ValueError("unexpected pixel buffer length")

    # Inspect alpha variability
    have_alpha = False
    # quick sample a few positions
    sample_idx = [0, (w * h) // 4, (w * h) // 2, (3 * w * h) // 4, w * h - 1]
    avals = []
    for si in sample_idx:
        si = max(0, min(w * h - 1, int(si)))
        avals.append(float(pixels[4 * si + 3]))
    if max(avals) - min(avals) > 1e-6:
        have_alpha = True

    u_min = 1.0
    v_min = 1.0
    u_max = 0.0
    v_max = 0.0
    found = False

    thr = float(max(0.0, min(1.0, alpha_threshold)))

    # Iterate rows and columns; early bailouts when possible
    for j in range(h):
        base = j * w * 4
        v = (j + 0.5) / h
        for i in range(w):
            o = base + i * 4
            r, g, b, a = pixels[o], pixels[o + 1], pixels[o + 2], pixels[o + 3]
            ink = False
            if have_alpha:
                ink = a >= thr
            else:
                # fallback: dark regions are considered silhouette; use 1 - luminance
                lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
                ink = (1.0 - lum) >= thr
            if ink:
                u = (i + 0.5) / w
                if u < u_min:
                    u_min = u
                if u > u_max:
                    u_max = u
                if v < v_min:
                    v_min = v
                if v > v_max:
                    v_max = v
                found = True

    if not found:
        raise ValueError("no silhouette detected in image with given threshold")
    return (u_min, v_min, u_max, v_max), (w, h)


def _image_plane_dimensions(empty_obj) -> Tuple[float, float]:
    """Compute plane dimensions (width,height) in empty local units based on display size and image aspect."""
    size = float(getattr(empty_obj, "empty_display_size", 1.0))
    img = getattr(empty_obj, "data", None)
    if img is None:
        return size, size
    try:
        w = float(img.size[0])
        h = float(img.size[1])
        if w <= 0 or h <= 0:
            return size, size
        aspect = h / w
        return size, size * aspect
    except Exception:
        return size, size


def _project_bbox_on_empty_plane(obj, empty) -> Tuple[float, float, float, float]:
    """Project object's mesh to empty local XY plane and return bbox (minx,miny,maxx,maxy) in empty local units."""
    m_inv = empty.matrix_world.inverted()
    me = obj.data
    xs: list[float] = []
    ys: list[float] = []
    for v in me.vertices:
        p_local = m_inv @ obj.matrix_world @ v.co
        xs.append(float(p_local.x))
        ys.append(float(p_local.y))
    if not xs or not ys:
        return 0.0, 0.0, 0.0, 0.0
    return min(xs), min(ys), max(xs), max(ys)


def _compose_delta_world(empty, co_center, ci_center, sx, sy) -> Matrix:
    """Build world-space delta matrix that scales in empty-local XY by (sx,sy) around object's projected center and translates to image center."""
    M = empty.matrix_world.copy()
    Minv = M.inverted()
    T_to = Matrix.Translation(Vector((ci_center[0], ci_center[1], 0.0)))
    T_from = Matrix.Translation(Vector((-co_center[0], -co_center[1], 0.0)))
    S = Matrix.Diagonal(Vector((sx, sy, 1.0, 1.0)))
    delta_local = T_to @ S @ T_from
    return M @ delta_local @ Minv


def _image_sampling(img) -> Tuple[list, int, int, bool]:
    w = int(getattr(img, "size", [0, 0])[0])
    h = int(getattr(img, "size", [0, 0])[1])
    if w <= 0 or h <= 0:
        raise ValueError("invalid image dimensions")
    pixels = list(img.pixels)
    if len(pixels) < 4 * w * h:
        raise ValueError("unexpected pixel buffer length")
    # Detect alpha variability
    have_alpha = False
    sample_idx = [0, (w * h) // 4, (w * h) // 2, (3 * w * h) // 4, w * h - 1]
    avals = []
    for si in sample_idx:
        si = max(0, min(w * h - 1, int(si)))
        avals.append(float(pixels[4 * si + 3]))
    if max(avals) - min(avals) > 1e-6:
        have_alpha = True
    return pixels, w, h, have_alpha


def _sample_ink(pixels: list, w: int, h: int, u: float, v: float, have_alpha: bool, threshold: float) -> bool:
    # Clamp UV to [0,1]
    uu = max(0.0, min(1.0, u))
    vv = max(0.0, min(1.0, v))
    i = min(w - 1, int(uu * w))
    j = min(h - 1, int(vv * h))
    o = (j * w + i) * 4
    r = pixels[o]
    g = pixels[o + 1]
    b = pixels[o + 2]
    a = pixels[o + 3]
    if have_alpha:
        return a >= threshold
    # Fallback by luminance
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return (1.0 - lum) >= threshold


@command("reference.fit_bbox_to_blueprint")
@tool
def fit_bbox_to_blueprint(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    """Fit object's projected 2D bbox to blueprint image silhouette bbox for the given view.

    - Uses existing Empty Image for the view (front|left|top) created by ref.blueprints_setup.
    - If 'image' is provided, loads it (check_existing) and uses it instead of the Empty's assigned image.
    - Computes silhouette bbox via alpha threshold (fallback to luminance if alpha is uniform).
    - Projects object geometry into the Empty's local XY plane, computes bbox there,
      and applies a scale (uniform or per-axis) and translation so the bboxes match.
    - Avoids bpy.ops; applies transforms via matrix multiplication.
    """
    if bpy is None or Vector is None or Matrix is None:
        raise RuntimeError("Blender API not available")

    obj_name = str(params.get("object", ""))
    view = str(params.get("view", "front")).lower()
    img_path = params.get("image")
    threshold = float(params.get("threshold", 0.5))
    uniform_scale = bool(params.get("uniform_scale", False))

    if view not in {"front", "left", "top"}:
        raise ValueError("view must be one of front|left|top")
    threshold = max(0.0, min(1.0, threshold))

    obj = _get_mesh_object(obj_name)

    empty = _get_blueprint_empty(view)
    if empty is None:
        if not img_path:
            raise ValueError("no blueprint Empty found for view; provide 'image' path or run ref.blueprints_setup")
        # Create a temporary Empty purely for projection frame (not linked)
        empty = bpy.data.objects.new("_TMP_BP", None)
        empty.empty_display_type = 'IMAGE'
        empty.empty_display_size = 1.0
        # Not linked; used for transform math only

    # Resolve image to use
    img = None
    if img_path:
        img = _load_image(str(img_path))
    else:
        try:
            img = getattr(empty, "data", None)
        except Exception:
            img = None
        if img is None:
            raise ValueError("blueprint Empty has no image assigned; provide 'image'")

    # Compute silhouette bbox in normalized image space
    bbox_uv, (iw, ih) = _silhouette_bbox_from_image(img, threshold)

    # Convert to empty-local coordinates based on its plane dimensions
    plane_w, plane_h = _image_plane_dimensions(empty)
    iu_min, iv_min, iu_max, iv_max = bbox_uv
    img_minx = (iu_min - 0.5) * plane_w
    img_maxx = (iu_max - 0.5) * plane_w
    img_miny = (iv_min - 0.5) * plane_h
    img_maxy = (iv_max - 0.5) * plane_h

    # Object bbox before in empty-local plane
    ob_minx, ob_miny, ob_maxx, ob_maxy = _project_bbox_on_empty_plane(obj, empty)

    # Compute centers and extents
    ci_x = 0.5 * (img_minx + img_maxx)
    ci_y = 0.5 * (img_miny + img_maxy)
    co_x = 0.5 * (ob_minx + ob_maxx)
    co_y = 0.5 * (ob_miny + ob_maxy)
    img_w = max(1e-9, img_maxx - img_minx)
    img_h = max(1e-9, img_maxy - img_miny)
    ob_w = max(1e-9, ob_maxx - ob_minx)
    ob_h = max(1e-9, ob_maxy - ob_miny)

    sx = img_w / ob_w if ob_w > 1e-12 else 1.0
    sy = img_h / ob_h if ob_h > 1e-12 else 1.0
    sx = float(max(1e-4, min(1e4, sx)))
    sy = float(max(1e-4, min(1e4, sy)))
    if uniform_scale:
        s = min(sx, sy)
        sx, sy = s, s

    # Compose world delta transform: scale in empty-local XY around object's projected center; then translate to image center
    delta = _compose_delta_world(empty, (co_x, co_y), (ci_x, ci_y), sx, sy)

    # Apply and report translation delta for object origin
    before_loc = obj.matrix_world.translation.copy()
    obj.matrix_world = delta @ obj.matrix_world
    after_loc = obj.matrix_world.translation.copy()
    trans_world = (after_loc - before_loc)

    # Bboxes after
    ob2_minx, ob2_miny, ob2_maxx, ob2_maxy = _project_bbox_on_empty_plane(obj, empty)

    result = {
        "scale_applied": [sx, sy, 1.0],
        "translation_applied": [float(trans_world.x), float(trans_world.y), float(trans_world.z)],
        "bbox_image": [img_minx, img_miny, img_maxx, img_maxy],
        "bbox_object_before": [ob_minx, ob_miny, ob_maxx, ob_maxy],
        "bbox_object_after": [ob2_minx, ob2_miny, ob2_maxx, ob2_maxy],
        "image_size": [int(iw), int(ih)],
        "view": view,
    }

    log.info(
        "fit_bbox_to_blueprint obj=%s view=%s sx=%.4f sy=%.4f trans=(%.4f,%.4f,%.4f)",
        obj.name,
        view,
        sx,
        sy,
        result["translation_applied"][0],
        result["translation_applied"][1],
        result["translation_applied"][2],
    )
    return result


@command("reference.snap_silhouette_to_blueprint")
@tool
def snap_silhouette_to_blueprint(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    """Iteratively snap object's projected silhouette to the blueprint image edge for the given view.

    - Identifies candidate vertices from silhouette edges w.r.t. the view direction.
    - Projects vertices to blueprint plane (Empty local XY) and nudges them towards the silhouette boundary
      by scanning along the radial direction from the object's projected centroid.
    - Applies light Laplacian smoothing after each iteration to reduce jaggies.
    """
    if bpy is None or Vector is None or Matrix is None:
        raise RuntimeError("Blender API not available")

    obj_name = str(params.get("object", ""))
    view = str(params.get("view", "front")).lower()
    img_path = params.get("image")
    threshold = float(params.get("threshold", 0.5))
    max_iters = int(params.get("max_iters", 8))
    step = float(params.get("step", 0.02))
    smooth_lambda = float(params.get("smooth_lambda", 0.25))
    smooth_iters = int(params.get("smooth_iters", 1))
    mode = str(params.get("mode", "VERTEX")).upper()

    if view not in {"front", "left", "top"}:
        raise ValueError("view must be one of front|left|top")
    threshold = max(0.0, min(1.0, threshold))
    max_iters = max(1, min(50, max_iters))
    step = max(1e-5, min(1.0, step))
    smooth_lambda = max(0.0, min(1.0, smooth_lambda))
    smooth_iters = max(0, min(10, smooth_iters))

    obj = _get_mesh_object(obj_name)
    empty = _get_blueprint_empty(view)
    if empty is None and not img_path:
        raise ValueError("no blueprint Empty found; provide 'image' or run ref.blueprints_setup")
    if empty is None:
        empty = bpy.data.objects.new("_TMP_BP", None)
        empty.empty_display_type = 'IMAGE'
        empty.empty_display_size = 1.0

    # Resolve image to sample
    img = _load_image(str(img_path)) if img_path else getattr(empty, "data", None)
    if img is None:
        raise ValueError("no image available to sample")
    pixels, iw, ih, have_alpha = _image_sampling(img)

    # Projection helpers
    M = empty.matrix_world.copy()
    Minv = M.inverted()
    MW = obj.matrix_world.copy()
    MWinv = MW.inverted()
    plane_w, plane_h = _image_plane_dimensions(empty)

    def to_empty_local_world(v_co_obj: Vector) -> Vector:
        return Minv @ (MW @ v_co_obj)

    def from_empty_local_to_obj(delta_local_xy: Vector, base_co_obj: Vector) -> Vector:
        # del_local is (dx,dy,0) in empty-local; convert to object-space delta and add to base
        world_delta = M.to_3x3() @ delta_local_xy
        obj_delta = MWinv.to_3x3() @ world_delta
        return base_co_obj + obj_delta

    def uv_from_local_xy(x: float, y: float) -> Tuple[float, float]:
        u = x / max(1e-9, plane_w) + 0.5
        v = y / max(1e-9, plane_h) + 0.5
        return u, v

    # Build BMesh for editing
    bm = ctx.bm_from_object(obj)
    try:
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        # View direction from empty local +Z in world
        vdir_world = (M.to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized()

        # Identify silhouette edges: edges with two faces that flip facing across vdir, or boundary edges
        cand_verts: set[int] = set()
        for e in bm.edges:
            faces = list(e.link_faces)
            if not faces:
                # Loose edge — ignore
                continue
            if len(faces) == 1:
                # Boundary edge: include
                cand_verts.add(faces[0].verts[0].index)
                cand_verts.add(faces[0].verts[-1].index)
                cand_verts.add(e.verts[0].index)
                cand_verts.add(e.verts[1].index)
                continue
            f1, f2 = faces[0], faces[1]
            n1w = (MW.to_3x3() @ f1.normal).normalized()
            n2w = (MW.to_3x3() @ f2.normal).normalized()
            s1 = n1w.dot(vdir_world)
            s2 = n2w.dot(vdir_world)
            if s1 * s2 <= 0.0:
                cand_verts.add(e.verts[0].index)
                cand_verts.add(e.verts[1].index)

        # Fallback if no candidates: use extreme projected vertices
        if not cand_verts:
            proj = [(i, to_empty_local_world(v.co)) for i, v in enumerate(bm.verts)]
            xs = [p[1].x for p in proj]
            ys = [p[1].y for p in proj]
            xmin = min(xs)
            xmax = max(xs)
            ymin = min(ys)
            ymax = max(ys)
            for i, p in proj:
                if abs(p.x - xmin) < 1e-6 or abs(p.x - xmax) < 1e-6 or abs(p.y - ymin) < 1e-6 or abs(p.y - ymax) < 1e-6:
                    cand_verts.add(i)

        # Precompute projected centroid
        plist = [to_empty_local_world(bm.verts[i].co) for i in cand_verts]
        if plist:
            cx = sum(p.x for p in plist) / len(plist)
            cy = sum(p.y for p in plist) / len(plist)
        else:
            cx = 0.0
            cy = 0.0

        moved_total = 0
        disp_accum = 0.0
        eps_stop = 1e-4

        for it in range(max_iters):
            moved_this = 0
            disp_this = 0.0
            # Nudge candidates
            for idx in cand_verts:
                v = bm.verts[idx]
                p_el = to_empty_local_world(v.co)
                dir_vec = Vector((p_el.x - cx, p_el.y - cy, 0.0))
                if dir_vec.length < 1e-9:
                    continue
                dir_xy = dir_vec.xy
                dxy = Vector((dir_xy.x, dir_xy.y, 0.0)).normalized()
                # Determine inside/outside at current position
                u, vv = uv_from_local_xy(p_el.x, p_el.y)
                inside = _sample_ink(pixels, iw, ih, u, vv, have_alpha, threshold)
                # Search along ray up to a small number of steps to detect boundary crossing
                max_line_steps = 8
                found = False
                sign = 1.0 if inside else -1.0
                for k in range(1, max_line_steps + 1):
                    trial = Vector((p_el.x, p_el.y, 0.0)) + dxy * (sign * step * k)
                    uu, vv2 = uv_from_local_xy(trial.x, trial.y)
                    inside2 = _sample_ink(pixels, iw, ih, uu, vv2, have_alpha, threshold)
                    if inside2 != inside:
                        # Move one step towards boundary
                        new_xy = Vector((p_el.x, p_el.y, 0.0)) + dxy * (sign * step)
                        new_co = from_empty_local_to_obj(new_xy - Vector((p_el.x, p_el.y, 0.0)), v.co)
                        disp = (new_co - v.co).length
                        if disp > 0:
                            v.co = new_co
                            moved_this += 1
                            disp_this += disp
                        found = True
                        break
                if not found:
                    # Conservative small nudge
                    new_xy = Vector((p_el.x, p_el.y, 0.0)) + dxy * (sign * step * 0.5)
                    new_co = from_empty_local_to_obj(new_xy - Vector((p_el.x, p_el.y, 0.0)), v.co)
                    disp = (new_co - v.co).length
                    if disp > 0:
                        v.co = new_co
                        moved_this += 1
                        disp_this += disp

            # Optional Laplacian smoothing constrained to plane
            for _ in range(smooth_iters):
                for idx in list(cand_verts):
                    v = bm.verts[idx]
                    nbrs = [e.other_vert(v) for e in v.link_edges]
                    if not nbrs:
                        continue
                    p = to_empty_local_world(v.co)
                    avgx = 0.0
                    avgy = 0.0
                    n = 0
                    for nb in nbrs:
                        pp = to_empty_local_world(nb.co)
                        avgx += pp.x
                        avgy += pp.y
                        n += 1
                    avgx /= max(1, n)
                    avgy /= max(1, n)
                    nx = (1.0 - smooth_lambda) * p.x + smooth_lambda * avgx
                    ny = (1.0 - smooth_lambda) * p.y + smooth_lambda * avgy
                    tgt = Vector((nx, ny, 0.0))
                    new_co = from_empty_local_to_obj(tgt - Vector((p.x, p.y, 0.0)), v.co)
                    v.co = new_co

            bm.normal_update()

            moved_total += moved_this
            disp_accum += disp_this
            log.info(
                "snap_silhouette iter=%d moved=%d avg_disp=%.6f",
                it + 1,
                moved_this,
                (disp_this / max(1, moved_this)),
            )
            if moved_this == 0 or (disp_this / max(1, moved_this)) < eps_stop:
                max_iters = it + 1
                break

        avg_disp = disp_accum / max(1, moved_total)
    finally:
        ctx.bm_to_object(obj, bm)
        try:
            bpy.context.view_layer.update()
        except Exception:
            pass

    return {
        "moved_vertices": int(moved_total),
        "avg_displacement": float(avg_disp),
        "iters_used": int(max_iters),
    }


# ---- Outline extraction from alpha (marching squares + Douglas-Peucker) ----

def _dp_simplify(points: list[tuple[float, float]], tol: float) -> list[tuple[float, float]]:
    if len(points) <= 2:
        return points[:]

    def dist(a, b, p) -> float:
        # Perpendicular distance from p to segment ab
        ax, ay = a
        bx, by = b
        px, py = p
        vx, vy = bx - ax, by - ay
        wx, wy = px - ax, py - ay
        vlen2 = vx * vx + vy * vy
        if vlen2 <= 1e-30:
            # a == b
            dx = px - ax
            dy = py - ay
            return (dx * dx + dy * dy) ** 0.5
        t = max(0.0, min(1.0, (wx * vx + wy * vy) / vlen2))
        projx = ax + t * vx
        projy = ay + t * vy
        dx = px - projx
        dy = py - projy
        return (dx * dx + dy * dy) ** 0.5

    def rdp(pts: list[tuple[float, float]], s: int, e: int, tol: float, out: list[int]) -> None:
        if e <= s + 1:
            return
        a = pts[s]
        b = pts[e]
        max_d = -1.0
        idx = -1
        for i in range(s + 1, e):
            d = dist(a, b, pts[i])
            if d > max_d:
                max_d = d
                idx = i
        if max_d > tol:
            rdp(pts, s, idx, tol, out)
            out.append(idx)
            rdp(pts, idx, e, tol, out)

    keep = [0, len(points) - 1]
    rdp(points, 0, len(points) - 1, tol, keep)
    keep = sorted(set(keep))
    return [points[i] for i in keep]


def _poly_area(points: list[tuple[float, float]]) -> float:
    a = 0.0
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return 0.5 * a


@command("reference.outline_from_alpha")
@tool
def outline_from_alpha(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    """Extract main silhouette outline from image alpha via marching squares and simplify.

    Returns: { points2d: [[x,y],...], width, height, scale_hint }
    """
    if bpy is None:
        raise RuntimeError("Blender API not available")

    path = str(params.get("image", ""))
    threshold = float(params.get("threshold", 0.5))
    simplify_tol = float(params.get("simplify_tol", 2.0))
    max_points = int(params.get("max_points", 2048))
    if not path:
        raise ValueError("image path is required")
    threshold = max(0.0, min(1.0, threshold))
    simplify_tol = max(0.0, min(1e6, simplify_tol))
    max_points = max(16, min(100_000, max_points))

    img = _load_image(path)
    w = int(getattr(img, "size", [0, 0])[0])
    h = int(getattr(img, "size", [0, 0])[1])
    if w <= 0 or h <= 0:
        raise ValueError("invalid image dimensions")

    # Build alpha mask
    pix = list(img.pixels)
    alphas = [pix[i + 3] for i in range(0, 4 * w * h, 4)]
    mask = [1 if a >= threshold else 0 for a in alphas]

    # Marching squares: generate segments
    def pt_key(x: float, y: float) -> tuple[int, int]:
        return (int(round(x * 2.0)), int(round(y * 2.0)))

    def add_seg(segments, p1, p2):
        segments.append((p1, p2))

    segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for j in range(h - 1):
        for i in range(w - 1):
            bl = mask[j * w + i]
            br = mask[j * w + (i + 1)]
            tl = mask[(j + 1) * w + i]
            tr = mask[(j + 1) * w + (i + 1)]
            code = (tl << 3) | (tr << 2) | (br << 1) | bl
            if code == 0 or code == 15:
                continue
            L = (i, j + 0.5)
            R = (i + 1, j + 0.5)
            B = (i + 0.5, j)
            T = (i + 0.5, j + 1)
            if code in (1, 14):
                add_seg(segments, L, B)
            elif code in (2, 13):
                add_seg(segments, B, R)
            elif code in (3, 12):
                add_seg(segments, L, R)
            elif code in (4, 11):
                add_seg(segments, T, R)
            elif code == 5:
                add_seg(segments, T, L)
                add_seg(segments, B, R)
            elif code in (6, 9):
                add_seg(segments, B, T)
            elif code == 7:
                add_seg(segments, L, T)
            elif code == 8:
                add_seg(segments, L, T)
            elif code == 10:
                add_seg(segments, L, B)
                add_seg(segments, T, R)

    # Link segments into closed polylines
    adjacency: dict[tuple[int, int], list[tuple[int, int]]] = {}
    key_to_pt: dict[tuple[int, int], tuple[float, float]] = {}
    for p1, p2 in segments:
        k1 = pt_key(*p1)
        k2 = pt_key(*p2)
        key_to_pt[k1] = p1
        key_to_pt[k2] = p2
        adjacency.setdefault(k1, []).append(k2)
        adjacency.setdefault(k2, []).append(k1)

    polygons: list[list[tuple[float, float]]] = []
    visited_edges: set[tuple[tuple[int, int], tuple[int, int]]] = set()

    for start in list(adjacency.keys()):
        for nxt in list(adjacency.get(start, [])):
            edge = (start, nxt)
            if edge in visited_edges or (nxt, start) in visited_edges:
                continue
            # Trace loop
            path_keys = [start]
            curr = nxt
            prev = start
            visited_edges.add(edge)
            while True:
                path_keys.append(curr)
                nbrs = adjacency.get(curr, [])
                # pick neighbor that's not prev; if none, break
                cand = None
                for nb in nbrs:
                    if nb != prev and ((curr, nb) not in visited_edges):
                        cand = nb
                        break
                if cand is None:
                    break
                visited_edges.add((curr, cand))
                prev, curr = curr, cand
                if curr == start:
                    # closed
                    break
            if len(path_keys) >= 4 and path_keys[0] == path_keys[-1]:
                poly = [key_to_pt[k] for k in path_keys[:-1]]
                polygons.append(poly)

    if not polygons:
        raise ValueError("no outline detected (empty or threshold too high)")

    # Select the largest by absolute area
    areas = [abs(_poly_area(poly)) for poly in polygons]
    idx = max(range(len(polygons)), key=lambda i: areas[i])
    poly = polygons[idx]

    # Simplify polygon (Douglas-Peucker)
    if simplify_tol > 0.0:
        poly = _dp_simplify(poly, simplify_tol)

    # Ensure CCW
    if _poly_area(poly) < 0:
        poly = list(reversed(poly))

    # Limit number of points
    if len(poly) > max_points:
        step = max(1, len(poly) // max_points)
        poly = poly[::step]

    points2d = [[float(x), float(y)] for (x, y) in poly]
    scale_hint = 1.0 / max(1.0, float(max(w, h)))

    log.info(
        "outline_from_alpha file=%s size=%dx%d pts=%d (simplified)",
        os.path.basename(path),
        w,
        h,
        len(points2d),
    )
    return {"points2d": points2d, "width": int(w), "height": int(h), "scale_hint": float(scale_hint)}


@command("reference.reconstruct_from_alpha")
@tool
def reconstruct_from_alpha(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    """Reconstruct an extruded mesh from an image's alpha silhouette.

    Steps:
      1) Extract outline via reference.outline_from_alpha (marching squares + simplify).
      2) Build mesh via mesh.poly_extrude_from_outline using view/thickness.
    """
    if bpy is None:
        raise RuntimeError("Blender API not available")

    name = str(params.get("name", "FromAlpha"))
    image = str(params.get("image", ""))
    view = str(params.get("view", "front")).lower()
    thickness = float(params.get("thickness", 0.2))
    threshold = float(params.get("threshold", 0.5))
    simplify_tol = float(params.get("simplify_tol", 2.0))

    if not image:
        raise ValueError("image path is required")
    if view not in {"front", "left", "top"}:
        raise ValueError("view must be one of front|left|top")
    threshold = max(0.0, min(1.0, threshold))
    simplify_tol = max(0.0, min(1e6, simplify_tol))
    thickness = float(max(1e-5, min(1e4, abs(thickness))))

    # 1) Outline extraction
    o = outline_from_alpha(ctx, {"image": image, "threshold": threshold, "simplify_tol": simplify_tol})
    if o.get("status") != "ok":  # type: ignore[union-attr]
        # Bubble up error
        raise RuntimeError(f"outline_from_alpha failed: {o}")
    out = o["result"]  # type: ignore[index]
    points2d = out.get("points2d", [])
    if not isinstance(points2d, list) or len(points2d) < 3:
        raise ValueError("outline extraction yielded insufficient points")

    # 2) Mesh extrusion
    from .mesh import poly_extrude_from_outline  # local import to avoid cycles

    res = poly_extrude_from_outline(
        ctx,
        {
            "name": name,
            "points2d": points2d,
            "view": view,
            "thickness": thickness,
            "triangulate": True,
        },
    )
    if res.get("status") != "ok":  # type: ignore[union-attr]
        raise RuntimeError(f"poly_extrude_from_outline failed: {res}")

    obj_name = res["result"]["object_name"]  # type: ignore[index]

    log.info(
        "reconstruct_from_alpha img=%s view=%s thr=%.2f simp=%.2f pts=%d -> obj=%s",
        os.path.basename(image),
        view,
        threshold,
        simplify_tol,
        len(points2d),
        obj_name,
    )

    return {"object_name": obj_name, "points_used": int(len(points2d))}
