from __future__ import annotations

import json
import os
import shutil
import time
from typing import Any, Dict

try:
    import bpy  # type: ignore
    import bmesh  # type: ignore
except Exception:
    bpy = None  # type: ignore
    bmesh = None  # type: ignore

from mcp_blender_addon.server.context import SessionContext

# Ensure command modules load and register
from mcp_blender_addon.commands import (  # noqa: F401
    modeling as _modeling,
    modifiers_core as _modifiers_core,
    modeling_edit as _modeling_edit,
    topology_cleanup as _topology_cleanup,
    analysis_metrics as _analysis_metrics,
)

from mcp_blender_addon.commands.modeling import create_primitive
from mcp_blender_addon.commands.modifiers_core import add_mirror, add_subsurf, add_solidify, apply_all
from mcp_blender_addon.commands.modeling_edit import extrude_normal, bevel_edges
from mcp_blender_addon.commands.topology_cleanup import cleanup_basic
from mcp_blender_addon.commands.analysis_metrics import mesh_stats
from mcp_blender_addon.helpers.snapshot import capture_view


def _clean_scene() -> None:
    if bpy is None:
        return
    # Remove all objects
    for obj in list(bpy.data.objects):
        try:
            for coll in list(obj.users_collection):
                try:
                    coll.objects.unlink(obj)
                except Exception:
                    pass
            bpy.data.objects.remove(obj)
        except Exception:
            pass
    # Optionally purge orphaned meshes
    for me in list(bpy.data.meshes):
        try:
            if me.users == 0:
                bpy.data.meshes.remove(me)
        except Exception:
            pass


def _ensure_dirs() -> Dict[str, str]:
    base = os.path.join("Generated", "tests")
    screens = os.path.join(base, "screens")
    os.makedirs(screens, exist_ok=True)
    return {"base": base, "screens": screens}


def _non_manifold_edges(obj_name: str) -> int:
    obj = bpy.data.objects.get(obj_name)
    if obj is None or obj.type != "MESH":
        return -1
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.edges.ensure_lookup_table()
        return int(sum(1 for e in bm.edges if not e.is_manifold))
    finally:
        bm.free()


def run() -> int:
    if bpy is None:
        print("This test must be run inside Blender.")
        return 1

    ctx = SessionContext(has_bpy=True, executor=None)

    # Clean scene for idempotency
    _clean_scene()

    # Create cube
    name = "SmokeCube"
    res = create_primitive(ctx, {"kind": "cube", "params": {"size": 2.0}, "name": name})
    assert res["status"] == "ok", res
    obj_name = res["result"]["object_name"] if "object_name" in res["result"] else res["result"].get("object", name)

    # Add modifiers and apply
    r1 = add_mirror(ctx, {"object": obj_name, "axis": "X", "use_clip": True})
    assert r1["status"] == "ok", r1
    r2 = add_subsurf(ctx, {"object": obj_name, "levels": 1})
    assert r2["status"] == "ok", r2
    r3 = add_solidify(ctx, {"object": obj_name, "thickness": 0.05, "offset": 0.0})
    assert r3["status"] == "ok", r3
    r4 = apply_all(ctx, {"object": obj_name})
    assert r4["status"] == "ok", r4

    # Edit operations: extrude some faces and bevel some edges
    # Use a conservative selection to avoid non-manifold: first 6 faces, first 12 edges
    ex = extrude_normal(ctx, {"object": obj_name, "face_indices": list(range(6)), "amount": 0.05})
    assert ex["status"] == "ok", ex
    bv = bevel_edges(ctx, {"object": obj_name, "edge_indices": list(range(12)), "offset": 0.02, "segments": 2})
    assert bv["status"] == "ok", bv

    # Cleanup topology
    cl = cleanup_basic(ctx, {"object": obj_name, "merge_distance": 1e-5, "limited_angle": 0.349, "force_tris": False})
    assert cl["status"] == "ok", cl

    # Metrics
    met = mesh_stats(ctx, {"object": obj_name})
    assert met["status"] == "ok", met
    stats = met["result"]
    assert stats["counts"]["verts"] > 0 and stats["surface"]["area"] > 0.0
    assert stats["quality"]["edge_length"]["max"] >= stats["quality"]["edge_length"]["min"]

    # Verify non-manifold is zero after cleanup
    nm = _non_manifold_edges(obj_name)
    assert nm == 0, f"non-manifold edges: {nm}"

    # Screenshots
    dirs = _ensure_dirs()
    shots = {}
    for view in ("front", "top", "iso"):
        shot = capture_view(view=view, perspective=False, width=512, height=512, shading="SOLID", return_base64=False)
        path = shot.get("path")
        assert os.path.exists(path), f"snapshot missing: {path}"
        dest = os.path.join(dirs["screens"], f"{view}.png")
        try:
            shutil.move(path, dest)
        except Exception:
            shutil.copy2(path, dest)
        assert os.path.exists(dest) and os.path.getsize(dest) > 0
        shots[view] = dest

    # Log JSON summary
    summary = {
        "object": obj_name,
        "counts": stats["counts"],
        "area": stats["surface"]["area"],
        "volume": stats["surface"]["volume"],
        "edge_length": stats["quality"]["edge_length"],
        "screens": shots,
    }
    base = dirs["base"]
    os.makedirs(base, exist_ok=True)
    with open(os.path.join(base, "smoke_modeling_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # Clean end optionally keep the object for inspection
    # _clean_scene()
    print(json.dumps({"status": "ok", "summary": summary}))
    return 0


if __name__ == "__main__":
    code = run()
    raise SystemExit(code)

