from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

try:
    import bpy  # type: ignore
    import bmesh  # type: ignore
    from mathutils import Vector, Matrix, geometry  # type: ignore
except Exception:  # pragma: no cover
    bpy = None  # type: ignore
    bmesh = None  # type: ignore
    Vector = None  # type: ignore
    Matrix = None  # type: ignore
    geometry = None  # type: ignore

from ..server.registry import command, tool
from ..server.context import SessionContext
from ..server.logging import get_logger


log = get_logger(__name__)


def _get_mesh_object(name: str):
    if bpy is None:
        raise RuntimeError("Blender API not available")
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ValueError(f"object not found: {name}")
    if obj.type != "MESH":
        raise TypeError(f"object is not a mesh: {name}")
    return obj


def _world_bbox(obj) -> Tuple[List[float], List[float]]:  # type: ignore[override]
    try:
        corners = [obj.matrix_world @ Vector((c[0], c[1], c[2])) for c in obj.bound_box]
        xs = [v.x for v in corners]
        ys = [v.y for v in corners]
        zs = [v.z for v in corners]
        mn = [min(xs), min(ys), min(zs)]
        mx = [max(xs), max(ys), max(zs)]
        return mn, mx
    except Exception:
        return [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]


def _triangulate_area_world(verts_world: List[Vector]) -> float:
    # Expect a convex polygon provided as list; area via fan triangulation around v0
    if geometry is None:
        return 0.0
    if len(verts_world) < 3:
        return 0.0
    a = 0.0
    v0 = verts_world[0]
    for i in range(1, len(verts_world) - 1):
        v1 = verts_world[i]
        v2 = verts_world[i + 1]
        a += geometry.area_tri(v0, v1, v2)
    return float(a)


def _edge_lengths(bm, obj) -> List[float]:  # type: ignore[override]
    # World-space edge lengths
    m = obj.matrix_world
    out: List[float] = []
    try:
        for e in bm.edges:
            v0 = m @ e.verts[0].co
            v1 = m @ e.verts[1].co
            out.append((v1 - v0).length)
    except Exception:
        pass
    return out


def _percentiles(values: List[float], p_lo: float, p_hi: float) -> Tuple[float, float]:
    if not values:
        return 0.0, 0.0
    arr = sorted(values)
    n = len(arr)
    i_lo = max(0, min(n - 1, int(p_lo * (n - 1))))
    i_hi = max(0, min(n - 1, int(p_hi * (n - 1))))
    return float(arr[i_lo]), float(arr[i_hi])


def _avg_dihedral(bm) -> float:  # type: ignore[override]
    # Average angle between adjacent face normals over manifold edges
    total = 0.0
    cnt = 0
    try:
        for e in bm.edges:
            if len(e.link_faces) == 2:
                f1, f2 = e.link_faces
                try:
                    ang = f1.normal.angle(f2.normal)
                except Exception:
                    # Fallback using dot clamp
                    n1 = f1.normal.normalized()
                    n2 = f2.normal.normalized()
                    dot = max(-1.0, min(1.0, float(n1.dot(n2))))
                    ang = math.acos(dot)
                total += float(ang)
                cnt += 1
    except Exception:
        pass
    return float(total / cnt) if cnt else 0.0


@command("analysis.mesh_stats")
@tool
def mesh_stats(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    """Compute mesh metrics: counts, bbox, surface/volume, quality, symmetry.

    Returns a stable dict suitable for telemetry and UI.
    """
    if bpy is None or bmesh is None:
        raise RuntimeError("Blender API not available")

    obj = _get_mesh_object(str(params.get("object", "")))
    ctx.ensure_object_mode()

    me = obj.data
    counts = {
        "verts": int(len(me.vertices)),
        "edges": int(len(me.edges)),
        "faces": int(len(me.polygons)),
    }

    # BBox in world coordinates
    bb_min, bb_max = _world_bbox(obj)
    size = [bb_max[i] - bb_min[i] for i in range(3)]

    # Build a BMesh snapshot for geometric calculations
    bm = ctx.bm_from_object(obj)
    try:
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        tris = 0
        quads = 0
        ngons = 0
        for f in bm.faces:
            ln = len(f.verts)
            if ln == 3:
                tris += 1
            elif ln == 4:
                quads += 1
            elif ln > 4:
                ngons += 1
        counts.update({"tris": int(tris), "quads": int(quads), "ngons": int(ngons)})

        # Surface area (world-space) via triangulation
        area = 0.0
        m = obj.matrix_world
        for f in bm.faces:
            verts_world = [m @ v.co for v in f.verts]
            area += _triangulate_area_world(verts_world)

        # Volume: only if closed manifold (no boundary edges, all edges manifold)
        non_manifold = sum(1 for e in bm.edges if not e.is_manifold)
        has_boundary = any(e.is_boundary for e in bm.edges)
        volume = None
        if non_manifold == 0 and not has_boundary:
            try:
                # Sum signed volumes of triangles from origin
                vol = 0.0
                origin = Vector((0.0, 0.0, 0.0))
                for f in bm.faces:
                    vw = [m @ v.co for v in f.verts]
                    if len(vw) < 3:
                        continue
                    v0 = vw[0]
                    for i in range(1, len(vw) - 1):
                        v1 = vw[i]
                        v2 = vw[i + 1]
                        vol += (v0 - origin).cross(v1 - origin).dot(v2 - origin) / 6.0
                volume = abs(float(vol))
            except Exception as e:
                log.info("volume calc failed: %s", e)
                volume = None

        # Quality: avg dihedral, inverted faces by centroid test, edge length stats
        avg_dihedral = _avg_dihedral(bm)

        try:
            centroid = m @ bm.calc_center_median()
        except Exception:
            centroid = Vector((0.0, 0.0, 0.0))
        inverted = 0
        for f in bm.faces:
            try:
                c = m @ f.calc_center_median()
                n = (m.to_3x3() @ f.normal).normalized()
                if (c - centroid).dot(n) < 0:
                    inverted += 1
            except Exception:
                pass

        # Edge lengths
        lengths = _edge_lengths(bm, obj)
        if len(lengths) > 200_000:
            # sample first 200k for percentile estimation to keep time reasonable
            lengths_sample = lengths[:200_000]
        else:
            lengths_sample = lengths
        p01, p99 = _percentiles(lengths_sample, 0.01, 0.99)
        edge_stats = {
            "min": float(min(lengths)) if lengths else 0.0,
            "max": float(max(lengths)) if lengths else 0.0,
            "p01": float(p01),
            "p99": float(p99),
        }

        # Symmetry deviation: absolute mean coordinate in world space
        try:
            coords = [m @ v.co for v in bm.verts]
            if coords:
                mx = sum(v.x for v in coords) / len(coords)
                my = sum(v.y for v in coords) / len(coords)
                mz = sum(v.z for v in coords) / len(coords)
                symmetry = {"center_offset": [abs(mx), abs(my), abs(mz)]}
            else:
                symmetry = {"center_offset": [0.0, 0.0, 0.0]}
        except Exception:
            symmetry = {"center_offset": [0.0, 0.0, 0.0]}

    finally:
        ctx.bm_to_object(obj, bm)

    log.info(
        "mesh_stats obj=%s v=%d e=%d f=%d area=%.6f vol=%s avg_dih=%.4f",
        obj.name,
        counts["verts"],
        counts["edges"],
        counts["faces"],
        area,
        f"{volume:.6f}" if volume is not None else "None",
        avg_dihedral,
    )

    return {
        "counts": counts,
        "bbox": {"min": [float(x) for x in bb_min], "max": [float(x) for x in bb_max], "size": [float(x) for x in size]},
        "surface": {"area": float(area), "volume": (float(volume) if volume is not None else None)},
        "quality": {
            "avg_dihedral": float(avg_dihedral),
            "inverted_faces": int(inverted),
            "edge_length": edge_stats,
        },
        "symmetry": symmetry,
    }


@command("analysis.non_manifold_edges")
@tool
def non_manifold_edges(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    """Return the count of non-manifold edges for a mesh object.

    Params:
      - object: str (mesh object name)

    Returns: { count: int }

    Example:
      analysis.non_manifold_edges({"object":"Cube"}) -> {"status":"ok","result":{"count":0}}
    """
    if bpy is None or bmesh is None:
        raise RuntimeError("Blender API not available")

    obj = _get_mesh_object(str(params.get("object", "")))
    ctx.ensure_object_mode()
    bm = ctx.bm_from_object(obj)
    try:
        bm.edges.ensure_lookup_table()
        cnt = int(sum(1 for e in bm.edges if not e.is_manifold))
    finally:
        ctx.bm_to_object(obj, bm)
    return {"count": int(cnt)}
