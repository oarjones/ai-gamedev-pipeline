from __future__ import annotations

from typing import Any, Dict, List

try:
    import bpy  # type: ignore
except Exception:  # pragma: no cover
    bpy = None  # type: ignore

from ..server.registry import command, tool
from ..server.context import SessionContext
from ..server.logging import get_logger


log = get_logger(__name__)


def _unlink_and_remove_object(obj) -> None:  # type: ignore[override]
    try:
        for coll in list(getattr(obj, "users_collection", []) or []):
            try:
                coll.objects.unlink(obj)
            except Exception:
                pass
        bpy.data.objects.remove(obj, do_unlink=True)
    except Exception:
        # Fallback: attempt simple remove
        try:
            bpy.data.objects.remove(obj)
        except Exception:
            pass


@command("scene.remove_object")
@tool
def remove_object(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    """Remove a single object by name from the scene and purge its datablocks if orphaned.

    Params:
      - name: object name (string)

    Returns: { removed: bool }

    Example:
      scene.remove_object({"name": "Cube"}) -> {"status":"ok","result":{"removed":true}}
    """
    if bpy is None:
        raise RuntimeError("Blender API not available")

    name = str(params.get("name", ""))
    if not name:
        raise ValueError("name is required")

    obj = bpy.data.objects.get(name)
    if obj is None:
        return {"removed": False}

    _unlink_and_remove_object(obj)

    # Best-effort purge of orphans
    try:
        bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)  # type: ignore[attr-defined]
    except Exception:
        pass

    log.info("scene.remove_object name=%s", name)
    return {"removed": True}


@command("scene.clear")
@tool
def clear(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    """Clear the scene: remove all objects and purge orphaned meshes, images, materials and other data.

    Params: {}

    Returns: { objects_removed: int, meshes_purged: int, images_purged: int, materials_purged: int }

    Example:
      scene.clear({}) -> {"status":"ok","result":{"objects_removed":3,...}}
    """
    if bpy is None:
        raise RuntimeError("Blender API not available")

    # Ensure object mode to avoid edit-mode data leakage
    ctx.ensure_object_mode()

    # Remove objects
    objs = list(bpy.data.objects)
    removed = 0
    for obj in objs:
        try:
            _unlink_and_remove_object(obj)
            removed += 1
        except Exception:
            pass

    # Best-effort purge of orphans via operator (available in 4.x)
    try:
        bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)  # type: ignore[attr-defined]
    except Exception:
        # Manual purge for common datablocks
        pass

    # Manual purge pass
    meshes_purged = 0
    images_purged = 0
    materials_purged = 0
    try:
        for me in list(bpy.data.meshes):
            try:
                if me.users == 0:
                    bpy.data.meshes.remove(me)
                    meshes_purged += 1
            except Exception:
                pass
        for img in list(bpy.data.images):
            try:
                if img.users == 0 and not getattr(img, "packed_file", None):
                    bpy.data.images.remove(img)
                    images_purged += 1
            except Exception:
                pass
        for mat in list(getattr(bpy.data, "materials", []) or []):
            try:
                if mat.users == 0:
                    bpy.data.materials.remove(mat)
                    materials_purged += 1
            except Exception:
                pass
    except Exception:
        pass

    log.info(
        "scene.clear removed=%d meshes=%d images=%d materials=%d",
        removed,
        meshes_purged,
        images_purged,
        materials_purged,
    )
    return {
        "objects_removed": int(removed),
        "meshes_purged": int(meshes_purged),
        "images_purged": int(images_purged),
        "materials_purged": int(materials_purged),
    }

