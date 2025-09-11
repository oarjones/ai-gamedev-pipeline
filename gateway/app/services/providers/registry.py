from __future__ import annotations

from typing import Callable, Dict

from .base import IAgentProvider, SessionCtx


class ProviderRegistry:
    def __init__(self) -> None:
        self._fns: Dict[str, Callable[[SessionCtx], IAgentProvider]] = {}

    def register(self, name: str, factory: Callable[[SessionCtx], IAgentProvider]) -> None:
        self._fns[name] = factory

    def get(self, name: str, session: SessionCtx) -> IAgentProvider:
        fn = self._fns.get(name)
        if not fn:
            raise KeyError(f"Provider not registered: {name}")
        return fn(session)


registry = ProviderRegistry()

