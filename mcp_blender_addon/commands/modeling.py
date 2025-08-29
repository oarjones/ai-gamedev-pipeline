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


@command("modeling.create_primitive")
@tool
def create_primitive(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    if bpy is None:
        raise RuntimeError("Blender API not available")

    try:
        import bmesh  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError(f"bmesh unavailable: {e}")

    ptype = str(params.get("type", "cube")).lower()
    size = float(params.get("size", 1.0))
    name = params.get("name") or ptype.capitalize()
    if size <= 0:
        raise ValueError("size must be > 0")

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
    if bpy is None:
        raise RuntimeError("Blender API not available")

    obj_name = params.get("object")
    indices = params.get("face_indices")
    distance = float(params.get("distance", 0.0))
    if not isinstance(obj_name, str) or not isinstance(indices, (list, tuple)):
        raise ValueError("params must include 'object': str and 'face_indices': list[int]")
    face_indices = [int(i) for i in indices]

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

        # Average normal of selected faces
        avg = Vector((0.0, 0.0, 0.0))
        for f in faces:
            avg += f.normal
        if avg.length == 0.0:
            raise ValueError("average normal is zero; cannot extrude")
        avg.normalize()
        move_vec = avg * distance

        # Extrude region and translate the new geometry along avg normal
        res = bmesh.ops.extrude_face_region(bm, geom=faces)
        geom = res.get("geom", [])
        new_verts = [ele for ele in geom if isinstance(ele, bmesh.types.BMVert)]
        if new_verts:
            bmesh.ops.translate(bm, verts=new_verts, vec=move_vec)

        bm.normal_update()
        nfaces_after = len(bm.faces)
        created = max(0, nfaces_after - nfaces_before)
    finally:
        ctx.bm_to_object(obj, bm)
        ctx.ensure_object_mode()

    return {"object": obj.name, "created_faces": int(created)}
