from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Dict

try:
    import bpy  # type: ignore
    import bmesh  # type: ignore
except Exception:  # pragma: no cover
    bpy = None  # type: ignore
    bmesh = None  # type: ignore


try:
    import bpy  # type: ignore
except Exception:  # pragma: no cover
    bpy = None  # type: ignore


@dataclass
class AppContext:
    """Lightweight context object that can be passed to commands if needed."""

    has_bpy: bool

    @classmethod
    def detect(cls) -> "AppContext":
        return cls(has_bpy=bpy is not None)

    def blender_version(self) -> tuple[int, int, int] | None:
        if bpy is None:
            return None


# Session-scoped context passed to command tools
@dataclass
class SessionContext:
    has_bpy: bool
    executor: Optional["Executor"] = None

    # lightweight stores
    selection: Dict[str, Any] = field(default_factory=dict)
    snapshots: Dict[str, Any] = field(default_factory=dict)
    caches: Dict[str, Any] = field(default_factory=dict)

    def run_main(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        # If no executor or outside Blender, run directly
        if self.executor is None or not self.has_bpy:
            return fn(*args, **kwargs)
        # If we are already on the pump (main) thread, run directly
        try:
            if getattr(self.executor, "in_pump_thread")():  # type: ignore[attr-defined]
                return fn(*args, **kwargs)
        except Exception:
            pass
        # Otherwise, this is a misuse in our architecture (commands run in pump)
        raise RuntimeError("run_main called off main thread; use command enqueue path")

    # ---- Utilities (require bpy) ----

    def active_object(self):  # type: ignore[override]
        if bpy is None:
            return None
        return bpy.context.view_layer.objects.active

    def ensure_object_mode(self) -> str:
        if bpy is None:
            return "NONE"
        mode = getattr(bpy.context, "mode", "OBJECT")
        if mode != "OBJECT":
            try:
                bpy.ops.object.mode_set(mode="OBJECT")  # type: ignore[attr-defined]
            except Exception:
                pass
        return getattr(bpy.context, "mode", "OBJECT")

    def ensure_edit_mode(self, obj) -> str:  # type: ignore[override]
        if bpy is None:
            return "NONE"
        # Make object active and selected
        self.ensure_object_mode()
        try:
            for o in bpy.context.selected_objects:
                o.select_set(False)
        except Exception:
            pass
        try:
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.mode_set(mode="EDIT")  # type: ignore[attr-defined]
        except Exception:
            pass
        return getattr(bpy.context, "mode", "OBJECT")

    def bm_from_object(self, obj):  # type: ignore[override]
        if bpy is None or bmesh is None:
            raise RuntimeError("bmesh not available outside Blender")
        if obj is None or obj.type != "MESH":
            raise TypeError("bm_from_object: requires a mesh object")
        mesh = obj.data
        # If in edit mode for this mesh, use edit BM (do not free)
        if getattr(bpy.context, "mode", "OBJECT").startswith("EDIT") and bpy.context.view_layer.objects.active == obj:
            bm = bmesh.from_edit_mesh(mesh)
            setattr(bm, "_mcp_owned", False)
            return bm
        # Otherwise, create a new BM and load from mesh (must free later)
        bm = bmesh.new()
        bm.from_mesh(mesh)
        setattr(bm, "_mcp_owned", True)
        return bm

    def bm_to_object(self, obj, bm) -> None:  # type: ignore[override]
        if bpy is None or bmesh is None:
            return
        if obj is None or obj.type != "MESH":
            return
        mesh = obj.data
        owned = bool(getattr(bm, "_mcp_owned", False))
        if getattr(bpy.context, "mode", "OBJECT").startswith("EDIT") and bpy.context.view_layer.objects.active == obj:
            # Edit BM; just update edit mesh view
            try:
                bmesh.update_edit_mesh(mesh)
            except Exception:
                pass
        else:
            # Object mode; write back and free if owned
            bm.to_mesh(mesh)
            try:
                mesh.update()
            except Exception:
                pass
            if owned:
                bm.free()

try:
    # Type-only to avoid circular at runtime
    from .executor import Executor  # noqa: F401
except Exception:
    Executor = object  # type: ignore
        try:
            return tuple(bpy.app.version)  # type: ignore
        except Exception:
            return None
