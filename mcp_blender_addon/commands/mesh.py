from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

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


def _unique_name(existing, base: str) -> str:
    if base not in existing:
        return base
    i = 1
    while True:
        cand = f"{base}.{i:03d}"
        if cand not in existing:
            return cand
        i += 1


def _as_float3(v: Iterable[Any]) -> Tuple[float, float, float]:
    it = list(v)
    if len(it) != 3:
        raise ValueError("vertex must have exactly 3 components")
    try:
        return float(it[0]), float(it[1]), float(it[2])
    except Exception as e:
        raise ValueError(f"invalid vertex component: {e}")


def _validate_edges(edges: Optional[Iterable[Iterable[int]]], n: int) -> List[Tuple[int, int]]:
    if not edges:
        return []
    out: List[Tuple[int, int]] = []
    seen: set[Tuple[int, int]] = set()
    for e in edges:
        it = list(e)
        if len(it) != 2:
            raise ValueError("edge must be [i, j]")
        try:
            a = int(it[0])
            b = int(it[1])
        except Exception as ex:
            raise ValueError(f"edge indices must be int: {ex}")
        if a == b:
            continue
        if a < 0 or b < 0 or a >= n or b >= n:
            raise ValueError(f"edge index out of range: [{a}, {b}] with nverts={n}")
        key = (a, b) if a <= b else (b, a)
        if key in seen:
            continue
        seen.add(key)
        out.append((a, b))
    return out


def _validate_faces(faces: Optional[Iterable[Iterable[int]]], n: int) -> List[List[int]]:
    if not faces:
        return []
    out: List[List[int]] = []
    seen: set[Tuple[int, ...]] = set()
    for f in faces:
        it = [int(x) for x in list(f)]
        if len(it) < 3:
            continue
        # Check range and duplicates within face
        for idx in it:
            if idx < 0 or idx >= n:
                raise ValueError(f"face index out of range: {idx} with nverts={n}")
        if len(set(it)) != len(it):
            # Degenerate polygon with repeated indices; skip
            continue
        # Drop exact duplicate faces (same order) and simple reversed duplicates
        key = tuple(it)
        rkey = tuple(reversed(it))
        if key in seen or rkey in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def _poly_area2(points: List[Tuple[float, float]]) -> float:
    a = 0.0
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return 0.5 * a


def _segments_intersect(a1, a2, b1, b2) -> bool:
    def orient(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    def onseg(p, q, r):
        return min(p[0], r[0]) <= q[0] <= max(p[0], r[0]) and min(p[1], r[1]) <= q[1] <= max(p[1], r[1])

    o1 = orient(a1, a2, b1)
    o2 = orient(a1, a2, b2)
    o3 = orient(b1, b2, a1)
    o4 = orient(b1, b2, a2)
    if o1 == 0 and onseg(a1, b1, a2):
        return True
    if o2 == 0 and onseg(a1, b2, a2):
        return True
    if o3 == 0 and onseg(b1, a1, b2):
        return True
    if o4 == 0 and onseg(b1, a2, b2):
        return True
    return (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0)


def _is_simple_polygon2d(points: List[Tuple[float, float]]) -> bool:
    n = len(points)
    if n < 3:
        return False
    for i in range(n):
        a1 = points[i]
        a2 = points[(i + 1) % n]
        for j in range(i + 1, n):
            # Skip adjacent edges and the shared vertex between first and last
            if j == i or j == (i + 1) % n or (i == 0 and j == n - 1):
                continue
            b1 = points[j]
            b2 = points[(j + 1) % n]
            if _segments_intersect(a1, a2, b1, b2):
                return False
    return True


def _ear_clip_triangulate(points: List[Tuple[float, float]]) -> List[Tuple[int, int, int]]:
    # Returns list of triangle index tuples. Assumes simple polygon.
    n = len(points)
    if n < 3:
        return []
    idxs = list(range(n))

    def is_convex(i_prev, i_curr, i_next) -> bool:
        ax, ay = points[i_prev]
        bx, by = points[i_curr]
        cx, cy = points[i_next]
        return ((bx - ax) * (cy - ay) - (by - ay) * (cx - ax)) > 0

    def point_in_tri(px, py, ax, ay, bx, by, cx, cy) -> bool:
        # Barycentric technique
        v0x, v0y = cx - ax, cy - ay
        v1x, v1y = bx - ax, by - ay
        v2x, v2y = px - ax, py - ay
        den = v0x * v1y - v1x * v0y
        if abs(den) < 1e-20:
            return False
        u = (v2x * v1y - v1x * v2y) / den
        v = (v0x * v2y - v2x * v0y) / den
        return u >= -1e-12 and v >= -1e-12 and (u + v) <= 1.0 + 1e-12

    tris: List[Tuple[int, int, int]] = []
    guard = 0
    while len(idxs) > 3 and guard < 4 * n:
        ear_found = False
        m = len(idxs)
        for k in range(m):
            i_prev = idxs[(k - 1) % m]
            i_curr = idxs[k]
            i_next = idxs[(k + 1) % m]
            if not is_convex(i_prev, i_curr, i_next):
                continue
            ax, ay = points[i_prev]
            bx, by = points[i_curr]
            cx, cy = points[i_next]
            has_inside = False
            for j in idxs:
                if j in (i_prev, i_curr, i_next):
                    continue
                px, py = points[j]
                if point_in_tri(px, py, ax, ay, bx, by, cx, cy):
                    has_inside = True
                    break
            if has_inside:
                continue
            tris.append((i_prev, i_curr, i_next))
            del idxs[k]
            ear_found = True
            break
        if not ear_found:
            break
        guard += 1
    if len(idxs) == 3:
        tris.append((idxs[0], idxs[1], idxs[2]))
    # Fallback: if no triangles produced, simple fan
    if not tris and n >= 3:
        for k in range(1, n - 1):
            tris.append((0, k, k + 1))
    return tris


@command("mesh.from_points")
@tool
def from_points(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    """Create a mesh object from raw vertices and optional faces/edges.

    Params:
      - name: str
      - vertices: list[list[float]] size N x 3
      - faces: optional list[list[int]] (each len>=3)
      - edges: optional list[list[int]] (pairs)
      - collection: optional target collection name to link to
      - recalc_normals: bool (default True)

    Returns: { object_name, counts: { verts, edges, faces } }
    """
    if bpy is None:
        raise RuntimeError("Blender API not available")

    name = str(params.get("name", "MeshFromPoints"))
    vertices = params.get("vertices")
    faces = params.get("faces")
    edges = params.get("edges")
    collection_name = params.get("collection")
    recalc_normals = bool(params.get("recalc_normals", True))

    if not isinstance(vertices, (list, tuple)) or not vertices:
        raise ValueError("vertices must be a non-empty list of [x,y,z]")

    # Convert vertices to float3 list
    try:
        verts_f3 = [_as_float3(v) for v in vertices]  # type: ignore[arg-type]
    except Exception as e:
        raise ValueError(f"invalid vertices: {e}")

    n = len(verts_f3)
    edges_ij = _validate_edges(edges, n) if edges is not None else []
    faces_idx = _validate_faces(faces, n) if faces is not None else []

    if not edges_ij and not faces_idx:
        # If only vertices are provided, try to create only verts (no faces/edges)
        log.info("from_points: only vertices provided; creating point cloud object")

    # Create mesh datablock
    me = None
    obj = None
    created_mesh = False
    created_object = False
    try:
        mesh_name = _unique_name(bpy.data.meshes, name)
        me = bpy.data.meshes.new(mesh_name)
        created_mesh = True
        # from_pydata expects lists
        me.from_pydata(verts_f3, edges_ij, faces_idx)
        # Validate mesh and recalc normals if requested
        try:
            me.validate(verbose=True)
        except Exception:
            pass
        if recalc_normals:
            try:
                me.calc_normals()
            except Exception:
                pass
        try:
            me.update()
        except Exception:
            pass

        obj_name = _unique_name(bpy.data.objects, name)
        obj = bpy.data.objects.new(obj_name, me)
        created_object = True

        # Link to target collection
        if isinstance(collection_name, str) and collection_name.strip():
            col = bpy.data.collections.get(collection_name)
            if col is None:
                col = bpy.data.collections.new(collection_name)
                bpy.context.scene.collection.children.link(col)
        else:
            col = bpy.context.collection or bpy.context.scene.collection
        col.objects.link(obj)

        # Update depsgraph/view layer
        try:
            bpy.context.view_layer.update()
        except Exception:
            pass

        counts = {"verts": len(me.vertices), "edges": len(me.edges), "faces": len(me.polygons)}
        log.info("mesh.from_points name=%s v=%d e=%d f=%d", obj.name, counts["verts"], counts["edges"], counts["faces"])
        return {"object_name": obj.name, "counts": counts}
    except Exception:
        # Rollback on failure
        try:
            if created_object and obj is not None:
                bpy.data.objects.remove(obj, do_unlink=True)
        except Exception:
            pass
        try:
            if created_mesh and me is not None and me.users == 0:
                bpy.data.meshes.remove(me)
    except Exception:
        pass
        raise


@command("mesh.validate_and_heal")
@tool
def validate_and_heal(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    """Validate mesh data, weld near-duplicate vertices, optionally fix normals, and dissolve degenerate geometry.

    Params:
      - object: str (mesh object name)
      - weld_distance: float (merge by distance threshold, default 1e-5)
      - fix_normals: bool (recalculate normals, default True)
      - dissolve_threshold: float (degenerate dissolve distance, default 0.01)

    Returns: { merged_verts: int, dissolved_edges: int }
    """
    if bpy is None or bmesh is None:
        raise RuntimeError("Blender API not available")

    obj_name = str(params.get("object", ""))
    weld_distance = float(params.get("weld_distance", 1e-5))
    fix_normals = bool(params.get("fix_normals", True))
    dissolve_threshold = float(params.get("dissolve_threshold", 0.01))

    weld_distance = max(0.0, min(0.1, weld_distance))
    dissolve_threshold = max(0.0, min(1.0, dissolve_threshold))

    obj = _get_mesh_object(obj_name)
    ctx.ensure_object_mode()

    # First run Blender mesh.validate to clean data consistency
    try:
        obj.data.validate(verbose=True)
    except Exception:
        pass

    bm = ctx.bm_from_object(obj)
    try:
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        v_before = len(bm.verts)
        e_before = len(bm.edges)

        # Weld vertices by distance
        if weld_distance > 0.0 and v_before > 0:
            try:
                bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=weld_distance)
            except Exception:
                try:
                    bmesh.ops.weld_verts(bm, verts=bm.verts, dist=weld_distance)  # type: ignore[attr-defined]
                except Exception:
                    pass

        v_after = len(bm.verts)
        merged_verts = max(0, v_before - v_after)

        # Dissolve degenerate geometry based on distance
        if dissolve_threshold > 0.0 and len(bm.edges) > 0:
            try:
                bmesh.ops.dissolve_degenerate(bm, dist=dissolve_threshold)
            except Exception:
                pass

        e_after = len(bm.edges)
        dissolved_edges = max(0, e_before - e_after)

        # Recalculate normals if requested
        if fix_normals:
            try:
                bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            except Exception:
                pass
        bm.normal_update()
    finally:
        ctx.bm_to_object(obj, bm)
        try:
            bpy.context.view_layer.update()
        except Exception:
            pass

    log.info(
        "mesh.validate_and_heal obj=%s merged_verts=%d dissolved_edges=%d weld=%.6f dissolve=%.6f",
        obj.name,
        merged_verts,
        dissolved_edges,
        weld_distance,
        dissolve_threshold,
    )

    return {"merged_verts": int(merged_verts), "dissolved_edges": int(dissolved_edges)}


@command("mesh.poly_extrude_from_outline")
@tool
def poly_extrude_from_outline(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    """Create an extruded mesh from a 2D outline projected on a cardinal plane.

    Params:
      - name: str
      - points2d: list[[x,y], ...] CCW simple polygon
      - view: 'front'|'left'|'top' (plane mapping)
      - thickness: float (extrude amount along plane normal, default 0.2)
      - triangulate: bool (triangulate caps via ear clipping)
      - collection: optional collection name

    Returns: { object_name, counts: { verts, edges, faces } }
    """
    if bpy is None or bmesh is None:
        raise RuntimeError("Blender API not available")

    name = str(params.get("name", "Outline"))
    pts = params.get("points2d")
    view = str(params.get("view", "front")).lower()
    thickness = float(params.get("thickness", 0.2))
    triangulate = bool(params.get("triangulate", True))
    collection_name = params.get("collection")

    if not isinstance(pts, (list, tuple)) or len(pts) < 3:
        raise ValueError("points2d must be a list of at least 3 [x,y] points")
    if view not in {"front", "left", "top"}:
        raise ValueError("view must be one of front|left|top")
    thickness = float(max(1e-5, min(1e4, abs(thickness))))

    # Convert 2D points, ensure float, CCW, and simple
    pts2d: List[Tuple[float, float]] = []
    for p in pts:  # type: ignore[assignment]
        if not isinstance(p, (list, tuple)) or len(p) != 2:
            raise ValueError("each point must be [x,y]")
        try:
            pts2d.append((float(p[0]), float(p[1])))
        except Exception:
            raise ValueError("invalid point coordinate")
    if not _is_simple_polygon2d(pts2d):
        raise ValueError("points2d must define a simple (non self-intersecting) polygon")
    if _poly_area2(pts2d) < 0:
        pts2d = list(reversed(pts2d))

    # Mapping functions for plane
    if view == "front":
        to3d = lambda x, y: (x, y, 0.0)
        extrude_vec = (0.0, 0.0, thickness)
    elif view == "left":
        to3d = lambda x, y: (0.0, x, y)
        extrude_vec = (thickness, 0.0, 0.0)
    else:  # top
        to3d = lambda x, y: (x, 0.0, y)
        extrude_vec = (0.0, thickness, 0.0)

    bm = bmesh.new()
    try:
        # Create base vertices
        verts: List[Any] = []
        for x, y in pts2d:
            vx, vy, vz = to3d(x, y)
            verts.append(bm.verts.new((vx, vy, vz)))
        bm.verts.ensure_lookup_table()

        base_faces: List[Any] = []
        if triangulate:
            tris = _ear_clip_triangulate(pts2d)
            for i0, i1, i2 in tris:
                try:
                    f = bm.faces.new((verts[i0], verts[i1], verts[i2]))
                    base_faces.append(f)
                except ValueError:
                    pass
        else:
            try:
                f = bm.faces.new(tuple(verts))
                base_faces.append(f)
            except ValueError:
                # fallback: triangulate if polygon face exists
                tris = _ear_clip_triangulate(pts2d)
                for i0, i1, i2 in tris:
                    try:
                        f = bm.faces.new((verts[i0], verts[i1], verts[i2]))
                        base_faces.append(f)
                    except ValueError:
                        pass

        bm.faces.ensure_lookup_table()

        # Extrude region along normal axis direction
        res = bmesh.ops.extrude_face_region(bm, geom=base_faces)
        geom = res.get("geom", [])
        new_verts = [ele for ele in geom if isinstance(ele, bmesh.types.BMVert)]
        if new_verts:
            bmesh.ops.translate(bm, verts=new_verts, vec=extrude_vec)

        bm.normal_update()

        me = bpy.data.meshes.new(_unique_name(bpy.data.meshes, name))
        bm.to_mesh(me)
        me.update()
    finally:
        bm.free()

    obj_name = _unique_name(bpy.data.objects, name)
    obj = bpy.data.objects.new(obj_name, me)

    # Link to target collection
    if isinstance(collection_name, str) and collection_name.strip():
        col = bpy.data.collections.get(collection_name)
        if col is None:
            col = bpy.data.collections.new(collection_name)
            bpy.context.scene.collection.children.link(col)
    else:
        col = bpy.context.collection or bpy.context.scene.collection
    col.objects.link(obj)

    try:
        me.validate(verbose=True)
        me.calc_normals()
        bpy.context.view_layer.update()
    except Exception:
        pass

    counts = {"verts": len(me.vertices), "edges": len(me.edges), "faces": len(me.polygons)}
    log.info(
        "mesh.poly_extrude_from_outline name=%s view=%s v=%d e=%d f=%d",
        obj.name,
        view,
        counts["verts"],
        counts["edges"],
        counts["faces"],
    )
    return {"object_name": obj.name, "counts": counts}
