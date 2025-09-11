from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

try:
    import bpy  # type: ignore
    import bmesh  # type: ignore
    from mathutils import Vector, noise  # type: ignore
except Exception:  # pragma: no cover
    bpy = None  # type: ignore
    bmesh = None  # type: ignore
    Vector = None  # type: ignore
    noise = None  # type: ignore

from ..server.registry import command, tool
from ..server.context import SessionContext
from ..server.logging import get_logger


log = get_logger(__name__)


def _unique_name(existing: Dict[str, Any], base: str) -> str:
    if base not in existing:
        return base
    i = 1
    while True:
        cand = f"{base}.{i:03d}"
        if cand not in existing:
            return cand
        i += 1


def _tile_segments(total: int, tiles: int) -> List[int]:
    # Split total segments across tiles as evenly as possible, summing to total
    base = total // tiles
    rem = total % tiles
    return [base + (1 if i < rem else 0) for i in range(tiles)]


def _generate_tile_mesh(
    name: str,
    size_x: float,
    size_y: float,
    seg_x: int,
    seg_y: int,
    origin_x: float,
    origin_y: float,
    seed: int,
    amplitude: float,
    lacunarity: float,
    gain: float,
) -> bpy.types.Object:  # type: ignore[name-defined]
    bm = bmesh.new()
    try:
        # grid spacing
        dx = size_x / float(seg_x)
        dy = size_y / float(seg_y)

        # Pre-create vertices row by row
        verts_grid: List[List[Any]] = []
        # Seed noise for determinism
        try:
            noise.seed_set(int(seed))  # type: ignore[attr-defined]
        except Exception:
            pass

        # fBm noise parameters
        octaves = 6
        lac = max(1.01, float(lacunarity))
        gn = max(0.0, min(0.999, float(gain)))
        amp0 = float(amplitude)
        # Frequency base scaled so that one noise unit roughly matches one Blender unit
        base_freq = 1.0 / max(1e-6, max(size_x, size_y)) * 2.0

        for j in range(seg_y + 1):
            row: List[Any] = []
            y = origin_y + j * dy
            for i in range(seg_x + 1):
                x = origin_x + i * dx
                # fBm using noise.noise; deterministic with seed_set and absolute position
                f = 1.0
                a = 1.0
                nsum = 0.0
                for _ in range(octaves):
                    try:
                        n = float(noise.noise(Vector((x * base_freq * f, y * base_freq * f, 0.0))))  # type: ignore[attr-defined]
                    except Exception:
                        n = 0.0
                    nsum += a * n
                    f *= lac
                    a *= gn
                z = amp0 * nsum
                v = bm.verts.new((x, y, z))
                row.append(v)
            verts_grid.append(row)

        bm.verts.ensure_lookup_table()

        # Create faces
        for j in range(seg_y):
            row0 = verts_grid[j]
            row1 = verts_grid[j + 1]
            for i in range(seg_x):
                v0 = row0[i]
                v1 = row0[i + 1]
                v2 = row1[i + 1]
                v3 = row1[i]
                try:
                    bm.faces.new((v0, v1, v2, v3))
                except ValueError:
                    # face may already exist due to duplicate input; ignore
                    pass

        bm.normal_update()

        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        me.update()
    finally:
        bm.free()

    obj = bpy.data.objects.new(name, me)
    return obj


@command("proc.terrain")
@tool
def terrain(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    """Procedurally generate a terrain as a grid displaced by fBm noise.

    Params:
      - width: float (default 50)
      - depth: float (default 50)
      - resolution: int quads per axis (default 128)
      - seed: int (default 0)
      - amplitude: float (default 5.0)
      - lacunarity: float (default 2.0)
      - gain: float (default 0.5)

    LOD/tiling: splits into tiles if resolution is large to avoid a single huge mesh.

    Returns: { object_name, tiles }
    """
    if bpy is None or bmesh is None or Vector is None or noise is None:
        raise RuntimeError("Blender API not available")

    width = float(params.get("width", 50.0))
    depth = float(params.get("depth", 50.0))
    res = int(params.get("resolution", 128))
    seed = int(params.get("seed", 0))
    amplitude = float(params.get("amplitude", 5.0))
    lacunarity = float(params.get("lacunarity", 2.0))
    gain = float(params.get("gain", 0.5))

    # Clamp & sanitize
    width = max(1e-3, min(10_000.0, width))
    depth = max(1e-3, min(10_000.0, depth))
    res = max(2, min(4096, res))
    amplitude = max(-1e4, min(1e4, amplitude))
    lacunarity = max(1.01, min(8.0, lacunarity))
    gain = max(0.0, min(0.999, gain))

    ctx.ensure_object_mode()

    # Determine tiling: keep per-tile segments under ~256 for memory/perf
    max_seg = 256
    tiles_u = max(1, (res + max_seg - 1) // max_seg)
    tiles_v = max(1, (res + max_seg - 1) // max_seg)
    segs_u = _tile_segments(res, tiles_u)
    segs_v = _tile_segments(res, tiles_v)

    # Compute per-tile sizes and origins so the full grid spans [-w/2..w/2], [-d/2..d/2]
    total_w = width
    total_d = depth
    # widths and depths per tile proportional to segment counts
    w_per_seg = total_w / float(res)
    d_per_seg = total_d / float(res)

    # Create parent empty for grouping
    parent_name = _unique_name(bpy.data.objects, f"Terrain_{seed}_{res}")
    parent = bpy.data.objects.new(parent_name, None)
    parent.empty_display_size = max(0.1, min(10.0, max(total_w, total_d) * 0.02))
    parent.empty_display_type = 'PLAIN_AXES'

    # Link parent and children into current collection
    collection = bpy.context.collection or bpy.context.scene.collection
    collection.objects.link(parent)

    # Starting corner at min x,y
    x0 = -total_w * 0.5
    y0 = -total_d * 0.5

    # Generate tiles row-major
    created: List[str] = []
    off_y = 0.0
    for j, seg_y in enumerate(segs_v):
        tile_h = seg_y * d_per_seg
        off_x = 0.0
        for i, seg_x in enumerate(segs_u):
            tile_w = seg_x * w_per_seg
            name = _unique_name(bpy.data.objects, f"TerrainTile_{seed}_{res}_{i}_{j}")
            obj = _generate_tile_mesh(
                name=name,
                size_x=tile_w,
                size_y=tile_h,
                seg_x=seg_x,
                seg_y=seg_y,
                origin_x=x0 + off_x,
                origin_y=y0 + off_y,
                seed=seed,
                amplitude=amplitude,
                lacunarity=lacunarity,
                gain=gain,
            )
            obj.parent = parent
            collection.objects.link(obj)
            created.append(obj.name)
            off_x += tile_w
        off_y += tile_h

    log.info(
        "proc.terrain seed=%s res=%s tiles=%dx%d verts~=%s faces~=%s",
        seed,
        res,
        tiles_u,
        tiles_v,
        (res + 1) * (res + 1),
        res * res,
    )

    return {"object_name": parent.name, "tiles": int(len(created))}

