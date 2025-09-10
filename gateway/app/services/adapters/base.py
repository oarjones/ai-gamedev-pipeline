"""AgentAdapter base contract for handling input/output transformation.

Adapters allow the gateway to support different agent CLIs or providers
without changing the rest of the system.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class StreamEvent:
    kind: str  # 'chat' | 'tool' | 'event'
    payload: Dict[str, Any]


class AgentAdapter:
    """Interface for agent adapters."""

    name: str = "base"

    def prepare_input(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Prepare the text to send to the underlying agent process."""
        return prompt

    def on_stream(self, line: str) -> List[StreamEvent]:
        """Parse a single stdout line into zero or more stream events."""
        return [StreamEvent(kind="chat", payload={"content": line})]

