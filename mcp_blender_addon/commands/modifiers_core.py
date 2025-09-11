from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    import bpy  # type: ignore
except Exception:  # pragma: no cover
    bpy = None  # type: ignore

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


def _mod_stack(obj) -> list:
    return list(obj.modifiers)


def _unique_mod_name(obj, base: str) -> str:
    name = base
    if name not in obj.modifiers:
        return name
    idx = 1
    while True:
        candidate = f"{base}.{idx:03d}"
        if candidate not in obj.modifiers:
            return candidate
        idx += 1


def _apply_mesh_from_evaluated(obj) -> bpy.types.Mesh:  # type: ignore[name-defined]
    depsgraph = bpy.context.evaluated_depsgraph_get()
    obj_eval = obj.evaluated_get(depsgraph)
    mesh_eval = obj_eval.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
    # Create a copy owned by bpy.data and clear temp
    new_me = mesh_eval.copy()
    obj_eval.to_mesh_clear()
    old_me = obj.data
    obj.data = new_me
    try:
        if old_me.users == 0:
            bpy.data.meshes.remove(old_me)
    except Exception:
        pass
    try:
        new_me.update()
    except Exception:
        pass
    return new_me


@command("mod.add_mirror")
@tool
def add_mirror(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    """Añade un modificador Mirror al objeto de malla indicado.

    Parámetros: { object: str, axis?: 'X'|'Y'|'Z'='X', use_clip?: bool=true, merge_threshold?: float=1e-4 }
    Devuelve: { object, modifier, type, index }
    """
    if bpy is None:
        raise RuntimeError("Blender API not available")

    obj_name = str(params.get("object", ""))
    axis = str(params.get("axis", "X")).upper()
    use_clip = bool(params.get("use_clip", True))
    merge_threshold = float(params.get("merge_threshold", 1e-4))
    merge_threshold = max(0.0, min(0.1, merge_threshold))

    obj = _get_mesh_object(obj_name)
    ctx.ensure_object_mode()

    mod_name = _unique_mod_name(obj, "Mirror")
    m = obj.modifiers.new(name=mod_name, type='MIRROR')
    # Axis flags
    ax = {'X': (True, False, False), 'Y': (False, True, False), 'Z': (False, False, True)}.get(axis, (True, False, False))
    # Support both tuple and individual attrs depending on Blender version
    try:
        m.use_axis = ax  # type: ignore[attr-defined]
    except Exception:
        try:
            m.use_axis_x, m.use_axis_y, m.use_axis_z = ax  # type: ignore[attr-defined]
        except Exception:
            pass
    try:
        m.use_clip = use_clip  # type: ignore[attr-defined]
    except Exception:
        pass
    try:
        m.use_mirror_merge = True  # type: ignore[attr-defined]
    except Exception:
        pass
    try:
        m.merge_threshold = merge_threshold  # type: ignore[attr-defined]
    except Exception:
        pass

    log.info("add_mirror obj=%s axis=%s clip=%s merge=%s name=%s", obj.name, axis, use_clip, merge_threshold, m.name)
    return {"object": obj.name, "modifier": m.name, "type": m.type, "index": _mod_stack(obj).index(m)}


@command("mod.add_subsurf")
@tool
def add_subsurf(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    """Añade un modificador Subsurf al objeto con el nivel indicado.

    Parámetros: { object: str, levels?: int=2 }
    Devuelve: { object, modifier, type, index }
    """
    if bpy is None:
        raise RuntimeError("Blender API not available")

    obj = _get_mesh_object(str(params.get("object", "")))
    levels = int(params.get("levels", 2))
    levels = max(0, min(6, levels))
    ctx.ensure_object_mode()

    m = obj.modifiers.new(name=_unique_mod_name(obj, "Subsurf"), type='SUBSURF')
    try:
        m.levels = levels  # type: ignore[attr-defined]
    except Exception:
        pass
    try:
        m.render_levels = max(levels, getattr(m, 'render_levels', levels))  # type: ignore[attr-defined]
    except Exception:
        pass
    log.info("add_subsurf obj=%s levels=%s name=%s", obj.name, levels, m.name)
    return {"object": obj.name, "modifier": m.name, "type": m.type, "index": _mod_stack(obj).index(m)}


@command("mod.add_solidify")
@tool
def add_solidify(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    if bpy is None:
        raise RuntimeError("Blender API not available")

    obj = _get_mesh_object(str(params.get("object", "")))
    thickness = float(params.get("thickness", 0.02))
    offset = float(params.get("offset", 0.0))
    thickness = max(-10.0, min(10.0, thickness))
    offset = max(-1.0, min(1.0, offset))
    ctx.ensure_object_mode()

    m = obj.modifiers.new(name=_unique_mod_name(obj, "Solidify"), type='SOLIDIFY')
    try:
        m.thickness = thickness  # type: ignore[attr-defined]
    except Exception:
        pass
    try:
        m.offset = offset  # type: ignore[attr-defined]
    except Exception:
        pass
    log.info("add_solidify obj=%s thickness=%s offset=%s name=%s", obj.name, thickness, offset, m.name)
    return {"object": obj.name, "modifier": m.name, "type": m.type, "index": _mod_stack(obj).index(m)}


@command("mod.add_boolean")
@tool
def add_boolean(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    """Añade un modificador Boolean y configura su operand (objeto o colección).

    Parámetros: { object: str, operation?: 'DIFFERENCE'|'UNION'|'INTERSECT'='DIFFERENCE', operand_object?: str, operand_collection?: str }
    Devuelve: { object, modifier, type, index }
    """
    if bpy is None:
        raise RuntimeError("Blender API not available")

    obj = _get_mesh_object(str(params.get("object", "")))
    op = str(params.get("operation", "DIFFERENCE")).upper()
    if op not in {"DIFFERENCE", "UNION", "INTERSECT"}:
        raise ValueError("operation must be one of DIFFERENCE|UNION|INTERSECT")

    operand_object = params.get("operand_object")
    operand_collection = params.get("operand_collection")
    if not operand_object and not operand_collection:
        raise ValueError("operand_object or operand_collection must be provided")

    ctx.ensure_object_mode()
    m = obj.modifiers.new(name=_unique_mod_name(obj, "Boolean"), type='BOOLEAN')
    try:
        m.operation = op  # type: ignore[attr-defined]
    except Exception:
        pass

    if operand_object:
        other = bpy.data.objects.get(str(operand_object))
        if other is None:
            raise ValueError(f"operand object not found: {operand_object}")
        try:
            m.object = other  # type: ignore[attr-defined]
        except Exception:
            raise ValueError("boolean modifier does not support 'object' on this Blender version")
    elif operand_collection:
        col = bpy.data.collections.get(str(operand_collection))
        if col is None:
            raise ValueError(f"operand collection not found: {operand_collection}")
        try:
            m.collection = col  # type: ignore[attr-defined]
        except Exception:
            raise ValueError("boolean modifier does not support 'collection' on this Blender version")

    log.info("add_boolean obj=%s op=%s operand_obj=%s operand_col=%s name=%s", obj.name, op, operand_object, operand_collection, m.name)
    return {"object": obj.name, "modifier": m.name, "type": m.type, "index": _mod_stack(obj).index(m)}


@command("mod.apply")
@tool
def apply_modifier(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    """Apply a single modifier by name using evaluated mesh; avoids bpy.ops.

    Emulates Blender behavior: applying a modifier removes that modifier and all
    those above it (earlier in the stack). Remaining modifiers stay and will
    evaluate on the baked mesh.
    """
    if bpy is None:
        raise RuntimeError("Blender API not available")

    obj = _get_mesh_object(str(params.get("object", "")))
    name = str(params.get("name", ""))
    if not name:
        raise ValueError("modifier 'name' is required")

    ctx.ensure_object_mode()
    mods = list(obj.modifiers)
    if not mods:
        return {"object": obj.name, "applied": [], "remaining": []}
    try:
        idx = next(i for i, m in enumerate(mods) if m.name == name)
    except StopIteration:
        raise ValueError(f"modifier not found: {name}")

    # Record original visibility flags to be safe (optional)
    orig_vis = [bool(getattr(m, 'show_viewport', True)) for m in mods]
    # Enable up to target, disable those after
    for i, m in enumerate(mods):
        try:
            m.show_viewport = True if i <= idx else False  # type: ignore[attr-defined]
        except Exception:
            pass

    _apply_mesh_from_evaluated(obj)

    # Remove modifiers up to and including idx
    to_remove = [m.name for m in mods[: idx + 1]]
    for nm in to_remove:
        try:
            md = obj.modifiers.get(nm)
            if md is not None:
                obj.modifiers.remove(md)
        except Exception:
            pass

    # Restore visibility for remaining
    remaining = list(obj.modifiers)
    for i, m in enumerate(remaining):
        try:
            # Map back to orig_vis: those after idx shift left by idx+1
            orig_i = idx + 1 + i
            m.show_viewport = orig_vis[orig_i] if orig_i < len(orig_vis) else True  # type: ignore[attr-defined]
        except Exception:
            pass

    log.info("apply modifier obj=%s applied=%s remaining=%s", obj.name, to_remove, [m.name for m in remaining])
    return {"object": obj.name, "applied": to_remove, "remaining": [m.name for m in remaining]}


@command("mod.apply_all")
@tool
def apply_all(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    """Aplica todos los modificadores del objeto evaluando la malla resultante.

    Parámetros: { object: str }
    Devuelve: { object, applied: list[str], remaining: list[str] }
    """
    if bpy is None:
        raise RuntimeError("Blender API not available")

    obj = _get_mesh_object(str(params.get("object", "")))
    ctx.ensure_object_mode()

    applied = [m.name for m in list(obj.modifiers)]
    if applied:
        _apply_mesh_from_evaluated(obj)
        try:
            obj.modifiers.clear()
        except Exception:
            for m in list(obj.modifiers):
                try:
                    obj.modifiers.remove(m)
                except Exception:
                    pass
    log.info("apply_all obj=%s applied=%s", obj.name, applied)
    return {"object": obj.name, "applied": applied, "remaining": [m.name for m in obj.modifiers]}
