from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable, Coroutine, Optional, Protocol


@dataclass
class SessionCtx:
    projectId: str
    sessionId: str
    contextPack: Optional[dict] = None
    toolCatalog: Optional[dict] = None


@dataclass
class ProviderEvent:
    kind: str  # 'token' | 'tool_call' | 'final' | 'error'
    payload: dict


EventCallback = Callable[[ProviderEvent], Coroutine[Any, Any, None]]


class IAgentProvider(Protocol):
    async def start(self, session: SessionCtx) -> None: ...
    async def stop(self) -> None: ...
    async def send(self, user_message: str) -> None: ...
    def onEvent(self, cb: EventCallback) -> None: ...
    def status(self) -> dict: ...

