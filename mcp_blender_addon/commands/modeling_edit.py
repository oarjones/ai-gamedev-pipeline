from __future__ import annotations

from typing import Any, Dict, List

try:
    import bpy  # type: ignore
    import bmesh  # type: ignore
    from mathutils import Vector  # type: ignore
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


def _counts_from_mesh(me) -> Dict[str, int]:  # type: ignore[override]
    return {
        "vertices": int(len(me.vertices)),
        "edges": int(len(me.edges)),
        "faces": int(len(me.polygons)),
    }


def _non_manifold_edges(bm) -> int:  # type: ignore[override]
    try:
        return int(sum(1 for e in bm.edges if not e.is_manifold))
    except Exception:
        return -1


@command("edit.extrude_normal")
@tool
def extrude_normal(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    """Extrude selected faces along their normals by an amount.

    Params: { object: str, face_indices: list[int], amount: float }
    Returns: { object, before: {...}, after: {...}, non_manifold: int, created_faces: int }
    """
    if bpy is None or bmesh is None:
        raise RuntimeError("Blender API not available")

    obj_name = str(params.get("object", ""))
    face_indices = params.get("face_indices", []) or []
    amount = float(params.get("amount", 0.0))
    if not isinstance(face_indices, (list, tuple)):
        raise ValueError("face_indices must be a list[int]")

    log.info("edit.extrude_normal obj=%s faces=%s amount=%s", obj_name, len(face_indices), amount)
    obj = _get_mesh_object(obj_name)

    ctx.ensure_object_mode()
    me = obj.data
    before = _counts_from_mesh(me)

    bm = ctx.bm_from_object(obj)
    try:
        bm.faces.ensure_lookup_table()
        max_idx = len(bm.faces) - 1
        faces = []
        for i in face_indices:
            ii = int(i)
            if ii < 0 or ii > max_idx:
                raise IndexError(f"face index out of range: {ii}")
            faces.append(bm.faces[ii])

        if not faces or abs(amount) <= 1e-12:
            nonm = _non_manifold_edges(bm)
            after = _counts_from_mesh(me)
            return {"object": obj.name, "before": before, "after": after, "non_manifold": nonm, "created_faces": 0}

        nfaces_before = len(bm.faces)
        if len(faces) == 1:
            f = faces[0]
            n = f.normal
            move = Vector((0.0, 0.0, 0.0))
            if n.length > 0:
                move = n.normalized() * amount
            res = bmesh.ops.extrude_face_region(bm, geom=[f])
            geom = res.get("geom", [])
            new_verts = [ele for ele in geom if isinstance(ele, bmesh.types.BMVert)]
            if new_verts and move.length > 0:
                bmesh.ops.translate(bm, verts=new_verts, vec=move)
        else:
            res = bmesh.ops.extrude_discrete_faces(bm, faces=faces)
            new_faces = res.get("faces", [])
            for nf in new_faces:
                n = nf.normal
                if n.length > 0 and abs(amount) > 0:
                    bmesh.ops.translate(bm, verts=list(nf.verts), vec=n.normalized() * amount)

        bm.normal_update()
        nfaces_after = len(bm.faces)
        created = max(0, nfaces_after - nfaces_before)
        nonm = _non_manifold_edges(bm)
    finally:
        ctx.bm_to_object(obj, bm)
        try:
            bpy.context.view_layer.update()
        except Exception:
            pass

    after = _counts_from_mesh(obj.data)
    return {"object": obj.name, "before": before, "after": after, "non_manifold": int(nonm), "created_faces": int(created)}


@command("edit.inset_region")
@tool
def inset_region(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    """Inset region for a set of faces using bmesh.ops.inset_region.

    Params: { object: str, face_indices: list[int], thickness: float, depth: float=0.0 }
    Returns: { object, before: {...}, after: {...}, non_manifold: int }
    """
    if bpy is None or bmesh is None:
        raise RuntimeError("Blender API not available")

    obj_name = str(params.get("object", ""))
    face_indices = params.get("face_indices", []) or []
    if not isinstance(face_indices, (list, tuple)):
        raise ValueError("face_indices must be a list[int]")
    thickness = float(params.get("thickness", 0.0))
    depth = float(params.get("depth", 0.0))

    log.info("edit.inset_region obj=%s faces=%s thickness=%s depth=%s", obj_name, len(face_indices), thickness, depth)
    obj = _get_mesh_object(obj_name)
    ctx.ensure_object_mode()
    me = obj.data
    before = _counts_from_mesh(me)

    bm = ctx.bm_from_object(obj)
    try:
        bm.faces.ensure_lookup_table()
        max_idx = len(bm.faces) - 1
        faces = []
        for i in face_indices:
            ii = int(i)
            if ii < 0 or ii > max_idx:
                raise IndexError(f"face index out of range: {ii}")
            faces.append(bm.faces[ii])

        if not faces or (abs(thickness) <= 1e-12 and abs(depth) <= 1e-12):
            nonm = _non_manifold_edges(bm)
            after = _counts_from_mesh(me)
            return {"object": obj.name, "before": before, "after": after, "non_manifold": nonm}

        bmesh.ops.inset_region(
            bm,
            faces=faces,
            thickness=abs(thickness),
            depth=depth,
            use_even_offset=True,
            use_boundary=True,
            use_outset=False,
        )
        bm.normal_update()
        nonm = _non_manifold_edges(bm)
    finally:
        ctx.bm_to_object(obj, bm)
        try:
            bpy.context.view_layer.update()
        except Exception:
            pass

    after = _counts_from_mesh(obj.data)
    return {"object": obj.name, "before": before, "after": after, "non_manifold": int(nonm)}


@command("edit.bevel_edges")
@tool
def bevel_edges(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    """Bevel a set of edges using bmesh.ops.bevel.

    Params: { object: str, edge_indices: list[int], offset: float, segments: int=2, clamp_overlap: bool=True }
    Returns: { object, before: {...}, after: {...}, non_manifold: int }
    """
    if bpy is None or bmesh is None:
        raise RuntimeError("Blender API not available")

    obj_name = str(params.get("object", ""))
    edge_indices = params.get("edge_indices", []) or []
    if not isinstance(edge_indices, (list, tuple)):
        raise ValueError("edge_indices must be a list[int]")
    offset = float(params.get("offset", 0.0))
    segments = int(params.get("segments", 2))
    clamp_overlap = bool(params.get("clamp_overlap", True))

    log.info("edit.bevel_edges obj=%s edges=%s offset=%s segments=%s clamp=%s", obj_name, len(edge_indices), offset, segments, clamp_overlap)
    obj = _get_mesh_object(obj_name)
    ctx.ensure_object_mode()
    me = obj.data
    before = _counts_from_mesh(me)

    bm = ctx.bm_from_object(obj)
    try:
        bm.edges.ensure_lookup_table()
        max_idx = len(bm.edges) - 1
        edges = []
        for i in edge_indices:
            ii = int(i)
            if ii < 0 or ii > max_idx:
                raise IndexError(f"edge index out of range: {ii}")
            edges.append(bm.edges[ii])

        if not edges or offset <= 1e-12 or segments < 1:
            nonm = _non_manifold_edges(bm)
            after = _counts_from_mesh(me)
            return {"object": obj.name, "before": before, "after": after, "non_manifold": nonm}

        bmesh.ops.bevel(
            bm,
            geom=edges,
            offset=offset,
            segments=max(1, segments),
            profile=0.5,
            vertex_only=False,
            clamp_overlap=clamp_overlap,
            affect='EDGES',
            loop_slide=True,
        )
        bm.normal_update()
        nonm = _non_manifold_edges(bm)
    finally:
        ctx.bm_to_object(obj, bm)
        try:
            bpy.context.view_layer.update()
        except Exception:
            pass

    after = _counts_from_mesh(obj.data)
    return {"object": obj.name, "before": before, "after": after, "non_manifold": int(nonm)}
