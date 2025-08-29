from __future__ import annotations

import functools
import traceback
from typing import Any, Callable, Dict, Optional

from .logging import get_logger


log = get_logger(__name__)

# Global command registry: name -> callable(ctx, params) -> normalized dict
COMMANDS: Dict[str, Callable[[Any, Dict[str, Any]], Dict[str, Any]]] = {}


def command(name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to register a callable under 'namespace.action'.

    Registers the function object provided (typically already wrapped by @tool)
    into the global COMMANDS dict. Rejects duplicate names.
    """

    if not isinstance(name, str) or "." not in name:
        raise ValueError("command name must be 'namespace.action'")

    def _decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        if name in COMMANDS:
            raise ValueError(f"duplicate command registration: {name}")
        COMMANDS[name] = fn  # type: ignore[assignment]
        log.info("Registered command: %s", name)
        return fn

    return _decorator


def tool(fn: Callable[..., Any]) -> Callable[..., Dict[str, Any]]:
    """Decorator to normalize tool responses.

    Tool functions must accept (ctx, params) where ctx is a SessionContext.
    Always returns a dict:
      - on success: {"status": "ok", "result": <fn return>}
      - on exception: {"status": "error", "tool": <name>, "message": str, "trace": str}
    """

    tool_name = getattr(fn, "__name__", "tool")

    @functools.wraps(fn)
    def _wrapped(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        try:
            result = fn(*args, **kwargs)
            return {"status": "ok", "result": result}
        except Exception as e:  # noqa: BLE001
            return {
                "status": "error",
                "tool": tool_name,
                "message": str(e),
                "trace": traceback.format_exc(),
            }

    return _wrapped


def get(name: str) -> Optional[Callable[[Any, Dict[str, Any]], Dict[str, Any]]]:
    """Fetch a registered command by name, or None if not found."""
    return COMMANDS.get(name)
