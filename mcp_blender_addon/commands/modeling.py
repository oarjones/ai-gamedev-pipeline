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
from ..server.logging import get_logger


log = get_logger(__name__)


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
    """Create a mesh primitive without bpy.ops and link it to a collection.

    Params (JSON object):
      - kind: "cube" | "uv_sphere" | "ico_sphere" | "cylinder" | "cone" | "torus" | "plane"
      - params: dict of shape parameters (see below)
      - collection: optional collection name to link object (created if missing)
      - name: optional object name; if omitted, a deterministic unique name is chosen

    Common transform params (applied to object):
      - location: [x, y, z] (default [0,0,0])
      - rotation: [rx, ry, rz] radians (default [0,0,0])
      - scale: [sx, sy, sz] (default [1,1,1])

    Shape params by kind (defaults in parentheses):
      - cube: size (2.0)
      - plane: size (2.0)
      - uv_sphere: radius (1.0), segments (32), rings (16)
      - ico_sphere: radius (1.0), subdivisions (2)
      - cylinder: radius (1.0), depth (2.0), segments (32), cap_ends (True)
      - cone: radius_bottom (1.0), radius_top (0.0), depth (2.0), segments (32), cap_ends (True)
      - torus: major_radius (1.0), minor_radius (0.25), segments (32), ring_segments (16)

    Returns: { object_name, vertices, edges, faces, bbox }
      - bbox: [minx, miny, minz, maxx, maxy, maxz] in world space
    """
    if bpy is None:
        raise RuntimeError("Blender API not available")

    try:
        import bmesh  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError(f"bmesh unavailable: {e}")

    kind = str(params.get("kind", "cube")).lower()
    shape_params = params.get("params", {}) or {}
    if not isinstance(shape_params, dict):
        raise ValueError("'params' must be a dict of shape parameters")
    collection_name = params.get("collection")
    name_hint = params.get("name")

    valid_kinds = {"cube", "uv_sphere", "ico_sphere", "cylinder", "cone", "torus", "plane"}
    if kind not in valid_kinds:
        raise ValueError(f"unsupported primitive kind: {kind}")

    def _flt(v: Any, default: float) -> float:
        try:
            return float(v)
        except Exception:
            return float(default)

    def _int(v: Any, default: int) -> int:
        try:
            return int(v)
        except Exception:
            return int(default)

    def _vec3(v: Any, default: tuple[float, float, float]) -> tuple[float, float, float]:
        try:
            if isinstance(v, (list, tuple)) and len(v) == 3:
                return (float(v[0]), float(v[1]), float(v[2]))
        except Exception:
            pass
        return default

    # Parse common transforms
    loc = _vec3(params.get("location"), (0.0, 0.0, 0.0))
    rot = _vec3(params.get("rotation"), (0.0, 0.0, 0.0))
    scl = _vec3(params.get("scale"), (1.0, 1.0, 1.0))

    # Ensure in object mode (avoid edit-mode data leaks)
    ctx.ensure_object_mode()

    # Create mesh and object
    base_name = name_hint if isinstance(name_hint, str) and name_hint.strip() else kind
    name = base_name
    if name in bpy.data.objects:
        # Deterministic suffixing similar to Blender (name.001, .002, ...)
        idx = 1
        while True:
            candidate = f"{base_name}.{idx:03d}"
            if candidate not in bpy.data.objects:
                name = candidate
                break
            idx += 1

    me = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, me)

    # Link to target collection
    if isinstance(collection_name, str) and collection_name.strip():
        col = bpy.data.collections.get(collection_name)
        if col is None:
            col = bpy.data.collections.new(collection_name)
            # link new collection to scene
            bpy.context.scene.collection.children.link(col)
    else:
        col = bpy.context.collection or bpy.context.scene.collection
    col.objects.link(obj)

    log.info(
        "create_primitive kind=%s params=%s collection=%s name_hint=%s loc=%s rot=%s scale=%s",
        kind,
        {k: shape_params.get(k) for k in list(shape_params)[:8]},  # log small preview
        collection_name,
        name_hint,
        loc,
        rot,
        scl,
    )

    # Build geometry via bmesh
    bm = bmesh.new()
    try:
        if kind == "cube":
            size = _flt(shape_params.get("size", 2.0), 2.0)
            bmesh.ops.create_cube(bm, size=1.0)
            if abs(size - 2.0) > 1e-9:
                s = size / 2.0  # since created cube is side-length 2.0 after size=1.0
                bmesh.ops.scale(bm, vec=(s, s, s), verts=bm.verts)

        elif kind == "plane":
            size = _flt(shape_params.get("size", 2.0), 2.0)
            bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5)
            if abs(size - 1.0) > 1e-9:
                # grid size=0.5 yields side-length 1.0; scale to desired size
                s = float(size)
                bmesh.ops.scale(bm, vec=(s, s, s), verts=bm.verts)

        elif kind == "uv_sphere":
            seg = _int(shape_params.get("segments", 32), 32)
            rings = _int(shape_params.get("rings", 16), 16)
            radius = _flt(shape_params.get("radius", 1.0), 1.0)
            bmesh.ops.create_uvsphere(bm, u_segments=max(3, seg), v_segments=max(2, rings))
            if abs(radius - 1.0) > 1e-9:
                bmesh.ops.scale(bm, vec=(radius, radius, radius), verts=bm.verts)

        elif kind == "ico_sphere":
            subdiv = _int(shape_params.get("subdivisions", 2), 2)
            radius = _flt(shape_params.get("radius", 1.0), 1.0)
            bmesh.ops.create_icosphere(bm, subdivisions=max(1, subdiv), radius=1.0)
            if abs(radius - 1.0) > 1e-9:
                bmesh.ops.scale(bm, vec=(radius, radius, radius), verts=bm.verts)

        elif kind == "cylinder":
            seg = _int(shape_params.get("segments", 32), 32)
            radius = _flt(shape_params.get("radius", 1.0), 1.0)
            depth = _flt(shape_params.get("depth", 2.0), 2.0)
            bmesh.ops.create_cone(
                bm,
                segments=max(3, seg),
                radius1=radius,
                radius2=radius,
                depth=depth,
                cap_ends=bool(shape_params.get("cap_ends", True)),
            )

        elif kind == "cone":
            seg = _int(shape_params.get("segments", 32), 32)
            r1 = _flt(shape_params.get("radius_bottom", 1.0), 1.0)
            r2 = _flt(shape_params.get("radius_top", 0.0), 0.0)
            depth = _flt(shape_params.get("depth", 2.0), 2.0)
            bmesh.ops.create_cone(
                bm,
                segments=max(3, seg),
                radius1=max(0.0, r1),
                radius2=max(0.0, r2),
                depth=depth,
                cap_ends=bool(shape_params.get("cap_ends", True)),
            )

        elif kind == "torus":
            seg = _int(shape_params.get("segments", 32), 32)
            rseg = _int(shape_params.get("ring_segments", 16), 16)
            major = _flt(shape_params.get("major_radius", 1.0), 1.0)
            minor = _flt(shape_params.get("minor_radius", 0.25), 0.25)
            bmesh.ops.create_torus(
                bm,
                segments=max(3, seg),
                ring_segments=max(3, rseg),
                major_radius=max(1e-6, major),
                minor_radius=max(1e-6, minor),
            )

        else:
            raise ValueError(f"unsupported primitive kind: {kind}")

        bm.to_mesh(me)
        me.update()
    finally:
        bm.free()

    # Apply object transforms
    obj.location = loc  # type: ignore[assignment]
    obj.rotation_euler = rot  # type: ignore[assignment]
    obj.scale = scl  # type: ignore[assignment]

    # Metrics
    vcount = len(me.vertices)
    ecount = len(me.edges)
    fcount = len(me.polygons)

    # World-space AABB from bound_box corners
    try:
        corners = [obj.matrix_world @ Vector((vtx[0], vtx[1], vtx[2])) for vtx in obj.bound_box]  # type: ignore[index]
        xs = [c[0] for c in corners]
        ys = [c[1] for c in corners]
        zs = [c[2] for c in corners]
        bbox = [min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)]
    except Exception:
        bbox = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

    return {
        "object_name": obj.name,
        "vertices": int(vcount),
        "edges": int(ecount),
        "faces": int(fcount),
        "bbox": [float(x) for x in bbox],
    }



