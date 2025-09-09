from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict


def _state_dir() -> Path:
    # Use current working directory or Blender file directory when available
    root = Path(os.getcwd())
    state = root / ".state"
    state.mkdir(parents=True, exist_ok=True)
    return state


def record_operation(command: str, params: Dict[str, Any], result: Dict[str, Any]) -> None:
    try:
        entry = {
            "command": command,
            "params": params,
            "result_keys": list(result.keys()),
        }
        log = _state_dir() / "blender_ops.jsonl"
        with log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, separators=(",", ":")) + "\n")
    except Exception:
        pass

