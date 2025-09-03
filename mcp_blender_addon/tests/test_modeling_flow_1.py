from __future__ import annotations

import json
import os
from typing import Dict

from mcp_blender_addon.server.context import SessionContext

# Ensure command modules load and register
from mcp_blender_addon.commands import (  # noqa: F401
    modeling as _modeling,
    modeling_edit as _modeling_edit,
    modifiers_core as _modifiers_core,
    topology_cleanup as _topology_cleanup,
    analysis_metrics as _analysis_metrics,
    scene as _scene,
)

from mcp_blender_addon.commands.scene import clear as scene_clear
from mcp_blender_addon.commands.modeling import create_primitive
from mcp_blender_addon.commands.modifiers_core import add_mirror, add_subsurf, add_solidify, apply_all
from mcp_blender_addon.commands.modeling_edit import extrude_normal, bevel_edges
from mcp_blender_addon.commands.topology_cleanup import cleanup_basic
from mcp_blender_addon.commands.analysis_metrics import mesh_stats, non_manifold_edges
from mcp_blender_addon.helpers.snapshot import capture_view_alias as capture_view


def _ensure_dirs() -> Dict[str, str]:
    base = os.path.join("Generated", "tests", "flow1")
    screens = os.path.join(base, "screens")
    os.makedirs(screens, exist_ok=True)
    return {"base": base, "screens": screens}


def run() -> int:
    ctx = SessionContext(has_bpy=True, executor=None)

    # 1) Clear scene
    sc = scene_clear(ctx, {})
    assert sc["status"] == "ok", sc

    # 2) Create primitive cube
    name = "Flow1Cube"
    res = create_primitive(ctx, {"kind": "cube", "params": {"size": 2.0}, "name": name})
    assert res["status"] == "ok", res
    obj_name = res["result"].get("object_name") or res["result"].get("object", name)  # type: ignore[assignment]

    # 3) Add modifiers and apply all
    assert add_mirror(ctx, {"object": obj_name, "axis": "X", "use_clip": True})["status"] == "ok"
    assert add_subsurf(ctx, {"object": obj_name, "levels": 1})["status"] == "ok"
    assert add_solidify(ctx, {"object": obj_name, "thickness": 0.05, "offset": 0.0})["status"] == "ok"
    assert apply_all(ctx, {"object": obj_name})["status"] == "ok"

    # 4) Edit mesh: extrude some faces then bevel some edges
    ex = extrude_normal(ctx, {"object": obj_name, "face_indices": list(range(4)), "amount": 0.05})
    assert ex["status"] == "ok", ex
    bv = bevel_edges(ctx, {"object": obj_name, "edge_indices": list(range(12)), "offset": 0.02, "segments": 2})
    assert bv["status"] == "ok", bv

    # 5) Topology cleanup (includes normals recalc) and validate
    cl = cleanup_basic(ctx, {"object": obj_name, "merge_distance": 1e-5, "limited_angle": 0.349, "force_tris": False})
    assert cl["status"] == "ok", cl
    stats = mesh_stats(ctx, {"object": obj_name})
    assert stats["status"] == "ok", stats
    nm = non_manifold_edges(ctx, {"object": obj_name})
    assert nm["status"] == "ok" and nm["result"]["count"] == 0, nm

    # 6) Snapshots from various views
    dirs = _ensure_dirs()
    shots: Dict[str, str] = {}
    for view in ("front", "top", "iso"):
        shot = capture_view(ctx, {"view": view, "perspective": (view == "iso"), "width": 512, "height": 512, "shading": "SOLID", "return_base64": False})
        assert shot["status"] == "ok", shot
        path = shot["result"]["path"]
        dest = os.path.join(dirs["screens"], f"{view}.png")
        try:
            os.replace(path, dest)
        except Exception:
            try:
                import shutil

                shutil.copy2(path, dest)
            except Exception:
                pass
        shots[view] = dest

    # 7) Summary JSON
    summary = {
        "object": obj_name,
        "counts": stats["result"]["counts"],
        "surface": stats["result"]["surface"],
        "edge_length": stats["result"]["quality"]["edge_length"],
        "screens": shots,
    }
    with open(os.path.join(dirs["base"], "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(json.dumps({"status": "ok", "flow": 1, "summary": summary}))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())

