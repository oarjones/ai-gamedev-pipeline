from __future__ import annotations

from typing import Any, Dict

try:
    import bpy  # type: ignore
    from mathutils import Vector  # type: ignore
    import bmesh  # type: ignore
except Exception:  # pragma: no cover
    bpy = None  # type: ignore

from ..server.registry import command, tool
from ..server.context import SessionContext
from ..server.validation import get_str, get_float, get_list_int, ParamError


@command("modeling.echo")
@tool
def echo(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    """Echo parameters back to the caller.

    Params: any JSON-serializable object
    Returns: { echo: <params> }
    """
    return {"echo": params}


@command("modeling.get_version")
@tool
def get_version(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    """Get Blender version, if available.

    Returns: { blender: [major, minor, patch] | null }
    """
    if bpy is None:
        return {"blender": None}
    return {"blender": list(getattr(bpy.app, "version", (0, 0, 0)))}


@command("modeling.create_primitive")
@tool
def create_primitive(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    """Create a primitive mesh using bmesh (no bpy.ops).

    Params:
      - type: "cube" | "cylinder" | "plane"
      - size: float (uniform scale, > 0)
      - name: optional object name
    Returns: { object: str, verts: int, faces: int }
    """
    if bpy is None:
        raise RuntimeError("Blender API not available")

    try:
        import bmesh  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError(f"bmesh unavailable: {e}")

    try:
        ptype = get_str(params, "type", default="cube").lower()
        size = get_float(params, "size", default=1.0, positive=True)
        name = get_str(params, "name", default=None, required=False) or ptype.capitalize()
    except ParamError as e:
        raise ValueError(str(e))

    ctx.ensure_object_mode()

    me = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, me)
    # Link to current collection
    col = bpy.context.collection or bpy.context.scene.collection
    col.objects.link(obj)

    bm = bmesh.new()
    try:
        if ptype == "cube":
            bmesh.ops.create_cube(bm, size=1.0)
        elif ptype == "cylinder":
            # Create a unit cylinder (radius 0.5, depth 1.0), then scale uniformly
            bmesh.ops.create_cone(
                bm,
                segments=16,
                radius1=0.5,
                radius2=0.5,
                depth=1.0,
                cap_ends=True,
            )
        elif ptype == "plane":
            bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5)
        else:
            raise ValueError(f"unsupported primitive type: {ptype}")

        # Uniform scale to requested size
        if size != 1.0:
            bmesh.ops.scale(bm, vec=(size, size, size), verts=bm.verts)

        bm.to_mesh(me)
        me.update()
    finally:
        bm.free()

    # Ensure object mode and set object active/selected
    ctx.ensure_object_mode()
    try:
        for o in bpy.context.selected_objects:
            o.select_set(False)
    except Exception:
        pass
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    return {
        "object": obj.name,
        "verts": len(me.vertices),
        "faces": len(me.polygons),
    }


@command("modeling.extrude_normal")
@tool
def extrude_normal(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    """Extrude selected faces along their average normal by distance.

    Params: { object: str, face_indices: list[int], distance: float }
    Returns: { object: str, created_faces: int }
    """
    if bpy is None:
        raise RuntimeError("Blender API not available")

    try:
        obj_name = get_str(params, "object", required=True)
        face_indices = get_list_int(params, "face_indices", required=True)
        distance = get_float(params, "distance", default=0.0)
    except ParamError as e:
        raise ValueError(str(e))

    obj = bpy.data.objects.get(obj_name)
    if obj is None or obj.type != "MESH":
        raise ValueError(f"object not found or not a mesh: {obj_name}")

    # Work in object mode to avoid edit-mode leaks
    ctx.ensure_object_mode()

    bm = ctx.bm_from_object(obj)
    try:
        bm.faces.ensure_lookup_table()
        nfaces_before = len(bm.faces)
        faces = []
        max_i = nfaces_before - 1
        for i in face_indices:
            if i < 0 or i > max_i:
                raise IndexError(f"face index out of range: {i}")
            faces.append(bm.faces[i])
        if not faces:
            raise ValueError("no faces to extrude")

        # If multiple faces with opposing normals are selected (e.g., cube 0..5),
        # the average may be zero. In Blender 4.5, the intended UX for
        # "extrude along normal" with multiple faces is to extrude each face
        # along its own normal. Use discrete face extrusion and translate each
        # new face accordingly.
        created = 0
        if len(faces) == 1:
            f = faces[0]
            move_vec = f.normal.normalized() * distance if f.normal.length > 0 else Vector((0.0, 0.0, 0.0))
            res = bmesh.ops.extrude_face_region(bm, geom=[f])
            geom = res.get("geom", [])
            new_verts = [ele for ele in geom if isinstance(ele, bmesh.types.BMVert)]
            if new_verts and move_vec.length > 0:
                bmesh.ops.translate(bm, verts=new_verts, vec=move_vec)
        else:
            # Discrete extrude returns a list of new faces corresponding to the
            # originals. Move each new face along its own normal.
            res = bmesh.ops.extrude_discrete_faces(bm, faces=faces)
            new_faces = res.get("faces", [])
            # Map original -> new by index order if lengths match; otherwise move all new faces by their normals
            for nf in new_faces:
                n = nf.normal
                if n.length > 0 and abs(distance) > 0:
                    mv = n.normalized() * distance
                    bmesh.ops.translate(bm, verts=list(nf.verts), vec=mv)

        bm.normal_update()
        nfaces_after = len(bm.faces)
        created = max(0, nfaces_after - nfaces_before)
    finally:
        ctx.bm_to_object(obj, bm)
        ctx.ensure_object_mode()

    return {"object": obj.name, "created_faces": int(created)}
