from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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
        try:
            return tuple(bpy.app.version)  # type: ignore
        except Exception:
            return None

