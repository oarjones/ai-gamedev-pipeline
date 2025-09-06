"""CLI-generic adapter that wraps simple CLIs with minimal conventions.

Rules:
- Input is sent as-is (normalize newlines).
- Output lines prefixed with 'JSON:' are parsed as JSON.
- Output lines that are valid JSON objects with 'tool' are mapped to kind='tool'.
- Otherwise, lines are mapped to kind='chat'.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .base import AgentAdapter, StreamEvent


class CLIGenericAdapter(AgentAdapter):
    name = "cli_generic"

    def prepare_input(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> str:
        s = (prompt or "").replace("\r\n", "\n").replace("\r", "\n")
        return s

    def on_stream(self, line: str) -> List[StreamEvent]:
        s = (line or "").strip()
        if not s:
            return []

        text = s
        if s.startswith("JSON:"):
            text = s[5:].strip()

        # Try parse JSON
        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                if "tool" in obj or obj.get("type") == "tool":
                    return [StreamEvent(kind="tool", payload=obj)]
                # Generic event wrapper
                return [StreamEvent(kind="event", payload=obj)]
        except Exception:
            pass

        # Fallback chat line
        return [StreamEvent(kind="chat", payload={"content": s})]

