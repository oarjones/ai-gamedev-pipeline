from __future__ import annotations

import json
import os
import shutil
from typing import Any, Dict

try:
    import bpy  # type: ignore
    import bmesh  # type: ignore
except Exception:  # pragma: no cover
    bpy = None  # type: ignore
    bmesh = None  # type: ignore

from mcp_blender_addon.server.context import SessionContext

# Ensure command modules load and register
from mcp_blender_addon.commands import (  # noqa: F401
    reference_blueprints as _reference_blueprints,
    reference as _reference,
    analysis_metrics as _analysis_metrics,
    modifiers_core as _modifiers,
    modeling as _modeling,
)

from mcp_blender_addon.commands.reference_blueprints import blueprints_setup
from mcp_blender_addon.commands.reference import (
    fit_bbox_to_blueprint,
    snap_silhouette_to_blueprint,
    reconstruct_from_alpha,
)
from mcp_blender_addon.commands.analysis_metrics import mesh_stats
from mcp_blender_addon.commands.modifiers_core import add_boolean, apply_modifier
from mcp_blender_addon.commands.modeling import create_primitive
from mcp_blender_addon.helpers.snapshot import capture_view


def _clean_scene() -> None:
    if bpy is None:
        return
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
    for me in list(bpy.data.meshes):
        try:
            if me.users == 0:
                bpy.data.meshes.remove(me)
        except Exception:
            pass
    for img in list(bpy.data.images):
        try:
            if img.users == 0 and not img.packed_file:
                bpy.data.images.remove(img)
        except Exception:
            pass


def _ensure_dirs() -> Dict[str, str]:
    base = os.path.join("Generated", "tests", "blueprints")
    screens = os.path.join(base, "screens")
    os.makedirs(screens, exist_ok=True)
    return {"base": base, "screens": screens}


def _make_silhouette_image(name: str, w: int = 128, h: int = 128) -> str:
    img = bpy.data.images.new(name=name, width=w, height=h, alpha=True, float_buffer=False)
    # Fill with transparent
    pix = [0.0] * (w * h * 4)
    # Draw a centered filled rectangle
    xmin = int(w * 0.25)
    xmax = int(w * 0.75)
    ymin = int(h * 0.2)
    ymax = int(h * 0.8)
    for j in range(ymin, ymax):
        for i in range(xmin, xmax):
            o = (j * w + i) * 4
            pix[o + 0] = 0.0  # R
            pix[o + 1] = 0.0  # G
            pix[o + 2] = 0.0  # B
            pix[o + 3] = 1.0  # A
    img.pixels[:] = pix
    # Save to disk in test folder
    dirs = _ensure_dirs()
    fpath = os.path.join(dirs["base"], f"{name}.png")
    try:
        img.filepath_raw = fpath
        img.file_format = 'PNG'
        img.save()
    except Exception:
        # Fallback: pack and write via save_render if needed
        pass
    return fpath


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
    _clean_scene()

    # Create base object
    base_name = "BPBase"
    cres = create_primitive(ctx, {"kind": "cube", "params": {"size": 2.0}, "name": base_name})
    assert cres["status"] == "ok", cres
    obj_name = cres["result"]["object_name"] if "object_name" in cres["result"] else cres["result"].get("object", base_name)

    # Create silhouette images for front/left/top
    img_front = _make_silhouette_image("bp_front", 128, 128)
    img_left = _make_silhouette_image("bp_left", 128, 128)
    img_top = _make_silhouette_image("bp_top", 128, 128)

    # Setup blueprints
    bps = blueprints_setup(ctx, {"front": img_front, "left": img_left, "top": img_top, "size": 2.0, "opacity": 0.5, "lock": True})
    assert bps["status"] == "ok", bps

    # Fit bbox to front blueprint
    fit = fit_bbox_to_blueprint(ctx, {"object": obj_name, "view": "front"})
    assert fit["status"] == "ok", fit

    # Snap silhouette a few iterations
    snap = snap_silhouette_to_blueprint(ctx, {"object": obj_name, "view": "front", "threshold": 0.5, "max_iters": 3, "step": 0.02})
    assert snap["status"] == "ok", snap

    # Reconstruct from alpha (left view) and boolean union with base
    rec = reconstruct_from_alpha(ctx, {"name": "FromAlpha", "image": img_left, "view": "left", "thickness": 0.1, "threshold": 0.5, "simplify_tol": 1.5})
    assert rec["status"] == "ok", rec
    new_obj = rec["result"]["object_name"]

    # Boolean union
    m = add_boolean(ctx, {"object": obj_name, "operation": "UNION", "operand_object": new_obj})
    assert m["status"] == "ok", m
    mod_name = m["result"]["modifier"]
    ap = apply_modifier(ctx, {"object": obj_name, "name": mod_name})
    assert ap["status"] == "ok", ap

    # Screenshots
    dirs = _ensure_dirs()
    for view in ("front", "top", "iso"):
        shot = capture_view(view=view, perspective=False, width=384, height=384, shading="SOLID", return_base64=False)
        path = shot.get("path")
        assert os.path.exists(path), f"snapshot missing: {path}"
        dest = os.path.join(dirs["screens"], f"bp_{view}.png")
        try:
            shutil.move(path, dest)
        except Exception:
            shutil.copy2(path, dest)
        assert os.path.exists(dest) and os.path.getsize(dest) > 0

    # Metrics and assertions
    met = mesh_stats(ctx, {"object": obj_name})
    assert met["status"] == "ok", met
    stats = met["result"]
    assert stats["counts"]["faces"] > 0, "No faces after processing"
    nm = _non_manifold_edges(obj_name)
    assert nm == 0, f"non-manifold edges present: {nm}"

    # Output summary log
    summary = {"object": obj_name, "counts": stats["counts"], "screens_dir": dirs["screens"]}
    with open(os.path.join(dirs["base"], "blueprints_fit_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # Cleanup new_obj
    try:
        o = bpy.data.objects.get(new_obj)
        if o is not None:
            bpy.data.objects.remove(o, do_unlink=True)
    except Exception:
        pass

    print(json.dumps({"status": "ok", "summary": summary}))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())

