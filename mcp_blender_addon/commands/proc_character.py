from __future__ import annotations

from typing import Any, Dict, List, Tuple

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


def _unique_name(existing, base: str) -> str:
    if base not in existing:
        return base
    i = 1
    while True:
        cand = f"{base}.{i:03d}"
        if cand not in existing:
            return cand
        i += 1


def _build_skeleton_mesh(name: str, dims: Dict[str, float], axis: str) -> bpy.types.Object:  # type: ignore[name-defined]
    """Create a stick-figure skeleton as a graph of edges in +X half (mirror will complete)."""
    bm = bmesh.new()
    try:
        torso_len = dims["torso_len"]
        head_len = dims["head_len"]
        arm_len = dims["arm_len"]
        leg_len = dims["leg_len"]
        body_width = dims["body_width"]
        body_depth = dims["body_depth"]

        # Axis mapping: by default mirror around X, so build right side at +X
        ax = axis.upper()
        sgn = 1.0  # side sign for the mirrored axis (we place positive side)
        # We'll use X for lateral regardless; mirror axis selects modifier axis

        # Central spine along Z
        pelvis = bm.verts.new((0.0, 0.0, 0.0))
        chest = bm.verts.new((0.0, 0.0, torso_len * 0.7))
        neck = bm.verts.new((0.0, 0.0, torso_len))
        head_top = bm.verts.new((0.0, 0.0, torso_len + head_len))
        bm.edges.new((pelvis, chest))
        bm.edges.new((chest, neck))
        bm.edges.new((neck, head_top))

        # Shoulder/arm (right side only)
        sh_x = max(0.05, body_width * 0.5)
        shoulder = bm.verts.new((sh_x, 0.0, torso_len * 0.9))
        elbow = bm.verts.new((sh_x + arm_len * 0.45, 0.0, torso_len * 0.7))
        wrist = bm.verts.new((sh_x + arm_len, 0.0, torso_len * 0.7))
        bm.edges.new((neck, shoulder))
        bm.edges.new((shoulder, elbow))
        bm.edges.new((elbow, wrist))

        # Leg (right side only)
        hip = bm.verts.new((0.0, 0.0, 0.0))
        knee = bm.verts.new((body_width * 0.15, 0.0, -leg_len * 0.5))
        ankle = bm.verts.new((body_width * 0.15, 0.0, -leg_len))
        bm.edges.new((pelvis, hip))
        bm.edges.new((hip, knee))
        bm.edges.new((knee, ankle))

        bm.normal_update()

        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        me.update()
    finally:
        bm.free()

    obj = bpy.data.objects.new(name, me)
    return obj


def _ensure_skin_layer(obj) -> Any:
    # Ensure mesh has a skin vertex layer after adding a Skin modifier
    try:
        layer = obj.data.skin_vertices[0]
        return layer
    except Exception:
        try:
            obj.data.skin_vertices.new()
            return obj.data.skin_vertices[0]
        except Exception:
            return None


@command("proc.character_base")
@tool
def character_base(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a base character mesh from a seeded edge skeleton using Skin+Mirror+Subsurf.

    Modifier order: Mirror → Skin → Subsurf (Mirror first so Skin operates on welded, mirrored skeleton).
    Proportions keys accepted: torso_len, head_len, arm_len, leg_len, body_width, body_depth.
    Values are scale multipliers relative to defaults and are clamped to [0.5, 2.0].
    """
    if bpy is None or bmesh is None:
        raise RuntimeError("Blender API not available")

    scale = float(params.get("scale", 1.0))
    scale = max(0.01, min(100.0, scale))
    proportions = params.get("proportions") or {}
    if not isinstance(proportions, dict):
        proportions = {}
    symmetry_axis = str(params.get("symmetry_axis", "X")).upper()
    if symmetry_axis not in {"X", "Y", "Z"}:
        symmetry_axis = "X"
    thickness = float(params.get("thickness", 0.02))
    thickness = max(0.002, min(0.5, thickness))

    # Base default proportions in Blender units
    base = {
        "torso_len": 1.1,
        "head_len": 0.35,
        "arm_len": 0.9,
        "leg_len": 1.2,
        "body_width": 0.4,
        "body_depth": 0.25,
    }
    dims: Dict[str, float] = {}
    for k, v in base.items():
        mul = proportions.get(k)
        try:
            mul = float(mul)
        except Exception:
            mul = 1.0
        # Clamp multipliers
        mul = max(0.5, min(2.0, mul))
        dims[k] = float(v) * mul * scale

    ctx.ensure_object_mode()

    name = _unique_name(bpy.data.objects, "CharacterBase")
    obj = _build_skeleton_mesh(name, dims, symmetry_axis)
    collection = bpy.context.collection or bpy.context.scene.collection
    collection.objects.link(obj)

    # Mirror first for symmetry; clip to weld at center
    mir = obj.modifiers.new(name="Mirror", type='MIRROR')
    try:
        if symmetry_axis == 'X':
            mir.use_axis = (True, False, False)  # type: ignore[attr-defined]
        elif symmetry_axis == 'Y':
            mir.use_axis = (False, True, False)  # type: ignore[attr-defined]
        else:
            mir.use_axis = (False, False, True)  # type: ignore[attr-defined]
    except Exception:
        try:
            mir.use_axis_x, mir.use_axis_y, mir.use_axis_z = (
                symmetry_axis == 'X', symmetry_axis == 'Y', symmetry_axis == 'Z'
            )  # type: ignore[attr-defined]
        except Exception:
            pass
    try:
        mir.use_clip = True  # type: ignore[attr-defined]
    except Exception:
        pass

    # Skin to give volume
    skin = obj.modifiers.new(name="Skin", type='SKIN')

    # Ensure the skin vertex layer exists; mark pelvis/root and set radii
    layer = _ensure_skin_layer(obj)
    try:
        data = layer.data if layer is not None else []  # type: ignore[assignment]
    except Exception:
        data = []
    # Map vertex roles by simple heuristics (indices as created in _build_skeleton_mesh order)
    # 0: pelvis, 1: chest, 2: neck, 3: head_top, 4.. : arm, leg chain in order created
    for i, sv in enumerate(data):
        # Reasonable default radius everywhere
        r = thickness
        # Slightly thicker torso and head
        if i in (0, 1, 2, 3):
            r = max(thickness * 1.8, thickness)
        sv.radius = (r, r)  # type: ignore[attr-defined]
        try:
            sv.use_root = (i == 0)  # pelvis as root
        except Exception:
            pass

    # Subsurf for smoothness
    sub = obj.modifiers.new(name="Subsurf", type='SUBSURF')
    try:
        sub.levels = 2  # type: ignore[attr-defined]
        sub.render_levels = max(sub.levels, getattr(sub, 'render_levels', 2))  # type: ignore[attr-defined]
    except Exception:
        pass

    # Final touch: keep object scale = 1.0; geometry already accounts for 'scale'
    obj.scale = (1.0, 1.0, 1.0)

    log.info(
        "proc.character_base axis=%s scale=%.3f thickness=%.3f dims=%s",
        symmetry_axis,
        scale,
        thickness,
        {k: round(v, 3) for k, v in dims.items()},
    )

    return {"object_name": obj.name}

