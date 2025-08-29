from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional


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

    def run_main(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        if self.executor is None:
            return fn(*args, **kwargs)
        return self.executor.submit(fn, *args, **kwargs)

try:
    # Type-only to avoid circular at runtime
    from .executor import Executor  # noqa: F401
except Exception:
    Executor = object  # type: ignore
        try:
            return tuple(bpy.app.version)  # type: ignore
        except Exception:
            return None
