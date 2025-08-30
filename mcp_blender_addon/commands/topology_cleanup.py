from __future__ import annotations

from math import pi
from typing import Any, Dict

try:
    import bpy  # type: ignore
    import bmesh  # type: ignore
except Exception:  # pragma: no cover
    bpy = None  # type: ignore
    bmesh = None  # type: ignore

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


def _count_non_manifold_edges(bm) -> int:  # type: ignore[override]
    try:
        return int(sum(1 for e in bm.edges if not e.is_manifold))
    except Exception:
        return -1


@command("topology.cleanup_basic")
@tool
def cleanup_basic(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    """Topology cleanup: merge by distance, limited dissolve by angle, optional triangulate, and recalc normals.

    Params:
      - object: str (mesh name)
      - merge_distance: float (>=0, default 1e-4)
      - limited_angle: float (radians, [0..pi], default 0.349 ~ 20deg)
      - force_tris: bool (default False) — triangulate all faces if True

    Returns: { removed_verts: int, dissolved_edges: int, tri_faces: int }
    """
    if bpy is None or bmesh is None:
        raise RuntimeError("Blender API not available")

    obj_name = str(params.get("object", ""))
    merge_distance = float(params.get("merge_distance", 1e-4))
    limited_angle = float(params.get("limited_angle", 0.349))
    force_tris = bool(params.get("force_tris", False))

    merge_distance = max(0.0, min(1.0, merge_distance))
    limited_angle = max(0.0, min(pi, limited_angle))

    obj = _get_mesh_object(obj_name)
    ctx.ensure_object_mode()
    me = obj.data

    bm = ctx.bm_from_object(obj)
    try:
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        v0 = len(bm.verts)
        e0_before_diss = len(bm.edges)

        # Merge by distance (remove doubles)
        if merge_distance > 0.0 and v0 > 0:
            try:
                bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=merge_distance)
            except Exception:
                # Some versions might use weld_verts; fallback
                try:
                    bmesh.ops.weld_verts(bm, verts=bm.verts, dist=merge_distance)  # type: ignore[attr-defined]
                except Exception:
                    pass

        v_after_merge = len(bm.verts)
        removed_verts = max(0, v0 - v_after_merge)

        # Limited dissolve
        if limited_angle > 0.0 and len(bm.edges) > 0:
            try:
                bmesh.ops.dissolve_limit(
                    bm,
                    angle_limit=limited_angle,
                    use_dissolve_boundaries=False,
                    verts=bm.verts,
                    edges=bm.edges,
                    delimit=set(),
                )
            except Exception:
                # As a fallback, try dissolve_degenerate to clean tiny edges
                try:
                    bmesh.ops.dissolve_degenerate(bm, dist=merge_distance)
                except Exception:
                    pass

        e_after_diss = len(bm.edges)
        dissolved_edges = max(0, e0_before_diss - e_after_diss)

        # Triangulate if requested
        if force_tris and len(bm.faces) > 0:
            try:
                bmesh.ops.triangulate(bm, faces=bm.faces, quad_method='BEAUTY', ngon_method='BEAUTY')
            except Exception:
                bmesh.ops.triangulate(bm, faces=bm.faces)

        # Recalculate normals outward/consistent
        try:
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        except Exception:
            pass
        bm.normal_update()

        tri_faces = int(sum(1 for f in bm.faces if len(f.verts) == 3))
        nonm = _count_non_manifold_edges(bm)

        log.info(
            "cleanup_basic obj=%s merge=%.6f angle=%.6f tris=%s removed_verts=%s dissolved_edges=%s tri_faces=%s non_manifold=%s",
            obj.name,
            merge_distance,
            limited_angle,
            force_tris,
            removed_verts,
            dissolved_edges,
            tri_faces,
            nonm,
        )
    finally:
        ctx.bm_to_object(obj, bm)
        try:
            bpy.context.view_layer.update()
        except Exception:
            pass

    return {
        "removed_verts": int(removed_verts),
        "dissolved_edges": int(dissolved_edges),
        "tri_faces": int(tri_faces),
    }

