from __future__ import annotations

from typing import Any, Callable, Dict

from .logging import get_logger


Handler = Callable[[Dict[str, Any]], Any]


class Registry:
    """Simple command registry mapping 'namespace.action' -> handler."""

    def __init__(self) -> None:
        self._handlers: Dict[str, Handler] = {}
        self._log = get_logger(__name__)

    def register(self, name: str, fn: Handler) -> None:
        if not isinstance(name, str) or "." not in name:
            raise ValueError("command name must be 'namespace.action'")
        self._handlers[name] = fn
        self._log.info("Registered command: %s", name)

    def dispatch(self, name: str, params: Dict[str, Any]) -> Any:
        fn = self._handlers.get(name)
        if not fn:
            raise KeyError(f"unknown command: {name}")
        return fn(params)

