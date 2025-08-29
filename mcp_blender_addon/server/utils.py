from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Tuple


@dataclass
class JsonMessage:
    command: str
    params: Dict[str, Any]


def parse_json_message(raw: str) -> Tuple[JsonMessage | None, str | None]:
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            return None, "invalid JSON root"
        cmd = data.get("command")
        params = data.get("params", {})
        if not isinstance(cmd, str):
            return None, "missing or invalid 'command'"
        if not isinstance(params, dict):
            return None, "'params' must be an object"
        return JsonMessage(command=cmd, params=params), None
    except Exception as e:  # pragma: no cover - simple helper
        return None, f"json error: {e}"


def ok(result: Any = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {"status": "ok"}
    if result is not None:
        out["result"] = result
    return out


def error(message: str, code: str | None = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {"status": "error", "error": message}
    if code:
        out["code"] = code
    return out

