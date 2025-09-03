from __future__ import annotations

import json
import os
from typing import Dict

from mcp_blender_addon.server.context import SessionContext

# Ensure commands register
from mcp_blender_addon.commands import (  # noqa: F401
    reference_blueprints as _reference_blueprints,
    reference as _reference,
    modeling as _modeling,
    modifiers_core as _modifiers,
    analysis_metrics as _analysis_metrics,
    scene as _scene,
)

from mcp_blender_addon.commands.scene import clear as scene_clear
from mcp_blender_addon.commands.modeling import create_primitive
from mcp_blender_addon.commands.reference_blueprints import blueprints_setup
from mcp_blender_addon.commands.reference import fit_bbox_to_blueprint, snap_silhouette_to_blueprint, reconstruct_from_alpha
from mcp_blender_addon.commands.modifiers_core import add_boolean, apply_modifier
from mcp_blender_addon.commands.analysis_metrics import mesh_stats, non_manifold_edges
from mcp_blender_addon.helpers.snapshot import capture_view_alias as capture_view


def _ensure_dirs() -> Dict[str, str]:
    base = os.path.join("Generated", "tests", "flow2")
    screens = os.path.join(base, "screens")
    os.makedirs(screens, exist_ok=True)
    return {"base": base, "screens": screens}


def _templates_root() -> str:
    # Expect blueprint images to live under project templates directory
    # e.g., templates/front.png, templates/left.png, templates/top.png
    here = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    # here points to project root (ai-gamedev-pipeline)
    # If tests are moved, adjust accordingly
    return os.path.join(here, "templates")


def run() -> int:
    ctx = SessionContext(has_bpy=True, executor=None)

    # 1) Clear scene
    assert scene_clear(ctx, {})["status"] == "ok"

    # 2) Create base object
    base_name = "Flow2Base"
    cres = create_primitive(ctx, {"kind": "cube", "params": {"size": 2.0}, "name": base_name})
    assert cres["status"] == "ok", cres
    obj_name = cres["result"].get("object_name") or cres["result"].get("object", base_name)  # type: ignore[assignment]

    # 3) Read images from templates and setup blueprints
    troot = _templates_root()
    img_front = os.path.join(troot, "front.png")
    img_left = os.path.join(troot, "left.png")
    img_top = os.path.join(troot, "top.png")
    bps = blueprints_setup(ctx, {"front": img_front, "left": img_left, "top": img_top, "size": 2.0, "opacity": 0.5, "lock": True})
    assert bps["status"] == "ok", bps

    # 4) Fit bbox to front
    fit = fit_bbox_to_blueprint(ctx, {"object": obj_name, "view": "front", "threshold": 0.5, "uniform_scale": False})
    assert fit["status"] == "ok", fit

    # 5) Iterate snapping silhouette towards blueprint edge (front view)
    snap = snap_silhouette_to_blueprint(ctx, {"object": obj_name, "view": "front", "threshold": 0.5, "max_iters": 5, "step": 0.02, "smooth_lambda": 0.25, "smooth_iters": 1})
    assert snap["status"] == "ok", snap

    # 6) Reconstruct from alpha (left view) and boolean union with base
    rec = reconstruct_from_alpha(ctx, {"name": "Flow2FromAlpha", "image": img_left, "view": "left", "thickness": 0.15, "threshold": 0.5, "simplify_tol": 2.0})
    assert rec["status"] == "ok", rec
    new_obj = rec["result"]["object_name"]

    m = add_boolean(ctx, {"object": obj_name, "operation": "UNION", "operand_object": new_obj})
    assert m["status"] == "ok", m
    ap = apply_modifier(ctx, {"object": obj_name, "name": m["result"]["modifier"]})
    assert ap["status"] == "ok", ap

    # 7) Snapshots ortho + perspective
    dirs = _ensure_dirs()
    shots: Dict[str, str] = {}
    for view, persp in (("front", False), ("left", False), ("top", False), ("iso", True)):
        shot = capture_view(ctx, {"view": view, "perspective": persp, "width": 512, "height": 512, "shading": "SOLID", "return_base64": False})
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

    # 8) Metrics and non-manifold
    met = mesh_stats(ctx, {"object": obj_name})
    assert met["status"] == "ok", met
    nm = non_manifold_edges(ctx, {"object": obj_name})
    assert nm["status"] == "ok", nm

    # 9) Save summary
    summary = {
        "object": obj_name,
        "counts": met["result"]["counts"],
        "non_manifold": nm["result"]["count"],
        "screens": shots,
        "blueprints": {"front": img_front, "left": img_left, "top": img_top},
    }
    with open(os.path.join(dirs["base"], "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(json.dumps({"status": "ok", "flow": 2, "summary": summary}))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())

