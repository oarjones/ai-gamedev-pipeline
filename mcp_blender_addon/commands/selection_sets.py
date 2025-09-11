from __future__ import annotations

import json
import time
from typing import Any, Dict, Iterable, List, Tuple

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


STORE_PROP_KEY = "mw_sel"


def _get_mesh_object(name: str):
    if bpy is None:
        raise RuntimeError("Blender API not available")
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ValueError(f"object not found: {name}")
    if obj.type != "MESH":
        raise TypeError(f"object is not a mesh: {name}")
    return obj


def _compress_indices(items: Iterable[int]) -> str:
    # Compact range encoding: 0-3,5,7-9
    arr = sorted({int(i) for i in items})
    if not arr:
        return ""
    ranges: List[Tuple[int, int]] = []
    start = prev = arr[0]
    for x in arr[1:]:
        if x == prev + 1:
            prev = x
            continue
        ranges.append((start, prev))
        start = prev = x
    ranges.append((start, prev))
    parts: List[str] = []
    for a, b in ranges:
        parts.append(f"{a}-{b}" if a != b else f"{a}")
    return ",".join(parts)


def _decompress_indices(s: str) -> List[int]:
    if not s:
        return []
    out: List[int] = []
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a_str, b_str = part.split("-", 1)
            a = int(a_str)
            b = int(b_str)
            if b < a:
                a, b = b, a
            out.extend(range(a, b + 1))
        else:
            out.append(int(part))
    return out


def _load_store(obj) -> Tuple[Dict[str, Any], int]:
    raw = obj.get(STORE_PROP_KEY)
    if not raw:
        return {"sets": {}}, 0
    try:
        data = json.loads(raw)
    except Exception:
        return {"sets": {}}, 0
    sets = data.get("sets", {}) if isinstance(data, dict) else {}
    counter = int(data.get("counter", 0)) if isinstance(data, dict) else 0
    return {"sets": sets}, counter


def _save_store(obj, sets: Dict[str, Any], counter: int) -> None:
    payload = json.dumps({"sets": sets, "counter": counter}, separators=(",", ":"))
    obj[STORE_PROP_KEY] = payload


def _next_id(counter: int) -> Tuple[str, int]:
    # Compact base36 id from a monotonically increasing counter
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    n = max(0, int(counter)) + 1
    x = n
    buf = []
    while x:
        x, r = divmod(x, 36)
        buf.append(alphabet[r])
    sel_id = "s" + ("".join(reversed(buf)) if buf else "0")
    return sel_id, n


def _domain_from_mode(mode: str) -> str:
    m = mode.upper()
    if m not in {"VERT", "EDGE", "FACE"}:
        raise ValueError("mode must be one of VERT|EDGE|FACE")
    return m


@command("selection.store")
@tool
def selection_store(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    """Serialize current selection of the given object and domain into an object-local store.

    Params: { object: str, mode: "VERT"|"EDGE"|"FACE" }
    Returns: { selection_id, mode, count }
    Stored format (in Object custom property 'mw_sel' as JSON):
      { "sets": { id: { "mode": str, "v"|"e"|"f": range_str, "t": epoch } }, "counter": int }
    """
    if bpy is None or bmesh is None:
        raise RuntimeError("Blender API not available")

    obj = _get_mesh_object(str(params.get("object", "")))
    mode = _domain_from_mode(str(params.get("mode", "FACE")))

    ctx.ensure_object_mode()
    bm = ctx.bm_from_object(obj)
    try:
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        if mode == "VERT":
            idxs = [i for i, v in enumerate(bm.verts) if v.select]
            key = "v"
        elif mode == "EDGE":
            idxs = [i for i, e in enumerate(bm.edges) if e.select]
            key = "e"
        else:  # FACE
            idxs = [i for i, f in enumerate(bm.faces) if f.select]
            key = "f"

        comp = _compress_indices(idxs)
        store, counter = _load_store(obj)
        sel_id, counter = _next_id(counter)
        store["sets"][sel_id] = {"mode": mode, key: comp, "t": int(time.time())}
        _save_store(obj, store["sets"], counter)
    finally:
        # No topology changes; just ensure edit mesh UI sync if needed
        ctx.bm_to_object(obj, bm)

    log.info("selection.store obj=%s mode=%s id=%s count=%s", obj.name, mode, sel_id, len(idxs))
    return {"selection_id": sel_id, "mode": mode, "count": int(len(idxs))}


@command("selection.restore")
@tool
def selection_restore(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    """Restore a stored selection on the given object.

    Params: { object: str, selection_id: str }
    Returns: { mode, count }
    """
    if bpy is None or bmesh is None:
        raise RuntimeError("Blender API not available")

    obj = _get_mesh_object(str(params.get("object", "")))
    sel_id = str(params.get("selection_id", ""))
    if not sel_id:
        raise ValueError("selection_id is required")

    data, _ = _load_store(obj)
    payload = data["sets"].get(sel_id)
    if not isinstance(payload, dict):
        raise ValueError(f"unknown selection_id: {sel_id}")
    mode = _domain_from_mode(str(payload.get("mode", "FACE")))

    if mode == "VERT":
        key = "v"
    elif mode == "EDGE":
        key = "e"
    else:
        key = "f"
    comp = str(payload.get(key, ""))
    idxs = _decompress_indices(comp)

    ctx.ensure_object_mode()
    bm = ctx.bm_from_object(obj)
    try:
        if mode == "VERT":
            bm.verts.ensure_lookup_table()
            for v in bm.verts:
                v.select = False
            max_idx = len(bm.verts) - 1
            count = 0
            for i in idxs:
                ii = int(i)
                if 0 <= ii <= max_idx:
                    bm.verts[ii].select = True
                    count += 1
        elif mode == "EDGE":
            bm.edges.ensure_lookup_table()
            for e in bm.edges:
                e.select = False
            max_idx = len(bm.edges) - 1
            count = 0
            for i in idxs:
                ii = int(i)
                if 0 <= ii <= max_idx:
                    bm.edges[ii].select = True
                    count += 1
        else:  # FACE
            bm.faces.ensure_lookup_table()
            for f in bm.faces:
                f.select = False
            max_idx = len(bm.faces) - 1
            count = 0
            for i in idxs:
                ii = int(i)
                if 0 <= ii <= max_idx:
                    bm.faces[ii].select = True
                    count += 1
    finally:
        ctx.bm_to_object(obj, bm)

    log.info("selection.restore obj=%s mode=%s id=%s count=%s", obj.name, mode, sel_id, count)
    return {"mode": mode, "count": int(count)}


@command("selection.by_angle")
@tool
def selection_by_angle(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    """Compute a face region grown by normal angle from seed faces and store it.

    Params: { object: str, seed_faces: list[int], max_angle: float }
    Returns: { selection_id, count }
    """
    if bpy is None or bmesh is None:
        raise RuntimeError("Blender API not available")

    obj = _get_mesh_object(str(params.get("object", "")))
    seeds = params.get("seed_faces", []) or []
    if not isinstance(seeds, (list, tuple)):
        raise ValueError("seed_faces must be list[int]")
    try:
        max_angle = float(params.get("max_angle", 0.349))
    except Exception:
        max_angle = 0.349
    if max_angle < 0.0:
        max_angle = 0.0

    ctx.ensure_object_mode()
    bm = ctx.bm_from_object(obj)
    try:
        bm.faces.ensure_lookup_table()
        max_idx = len(bm.faces) - 1
        queue: List[int] = []
        visited = set()
        for i in seeds:
            ii = int(i)
            if 0 <= ii <= max_idx:
                queue.append(ii)
                visited.add(ii)

        # BFS across adjacent faces using edge link_faces and normal angle threshold
        while queue:
            fi = queue.pop(0)
            f = bm.faces[fi]
            n1 = f.normal
            for e in f.edges:
                # link_faces returns faces sharing the edge; may include f itself
                linked = [lf for lf in e.link_faces if lf is not f]
                for lf in linked:
                    j = lf.index
                    if j in visited:
                        continue
                    n2 = lf.normal
                    try:
                        # Clamp dot to [-1,1] then compare angle via acos ~ use angle method if available
                        angle = n1.angle(n2)
                    except Exception:
                        # Fallback simple threshold on dot
                        dot = max(-1.0, min(1.0, float(n1.normalized().dot(n2.normalized())))) if (n1.length and n2.length) else 0.0
                        # Equivalent threshold: angle <= max_angle <=> dot >= cos(max_angle)
                        import math

                        angle = math.acos(dot)
                    if angle <= max_angle:
                        visited.add(j)
                        queue.append(j)

        idxs = sorted(visited)
        comp = _compress_indices(idxs)

        store, counter = _load_store(obj)
        sel_id, counter = _next_id(counter)
        store["sets"][sel_id] = {"mode": "FACE", "f": comp, "t": int(time.time())}
        _save_store(obj, store["sets"], counter)
        count = len(idxs)
    finally:
        ctx.bm_to_object(obj, bm)

    log.info("selection.by_angle obj=%s seeds=%s angle=%.4f id=%s count=%s", obj.name, len(seeds), max_angle, sel_id, count)
    return {"selection_id": sel_id, "count": int(count)}

