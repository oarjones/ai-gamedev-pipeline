"""Tools registry: load tool metadata and validate inputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict

try:  # Optional jsonschema validation
    import jsonschema  # type: ignore
except Exception:  # pragma: no cover
    jsonschema = None  # type: ignore


class ToolMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(description="Unique tool identifier")
    name: str = Field(description="Human readable name")
    category: str = Field(description="Tool category")
    description: Optional[str] = Field(default=None)
    schema: Dict[str, Any] = Field(description="JSON Schema for input validation")


class ToolsRegistry:
    def __init__(self, folder: Path | str = Path("gateway") / "tools") -> None:
        self.folder = Path(folder)
        self._cache: Dict[str, ToolMeta] = {}
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        self._cache.clear()
        if not self.folder.exists():
            self._loaded = True
            return
        for p in self.folder.glob("*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                meta = ToolMeta.model_validate(data)
                self._cache[meta.id] = meta
            except Exception:
                # skip invalid definitions
                continue
        self._loaded = True

    def list_tools(self) -> List[ToolMeta]:
        self._load()
        return list(self._cache.values())

    def get_tool(self, tool_id: str) -> Optional[ToolMeta]:
        self._load()
        return self._cache.get(tool_id)

    def validate_input(self, tool_id: str, input_data: Dict[str, Any]) -> None:
        meta = self.get_tool(tool_id)
        if not meta:
            raise ValueError(f"Unknown tool: {tool_id}")
        schema = meta.schema or {}
        if jsonschema is None:
            # Minimal structural check
            if not isinstance(input_data, dict):
                raise ValueError("Input must be an object")
            return
        try:
            jsonschema.validate(input_data, schema)  # type: ignore
        except Exception as e:  # pragma: no cover - depends on lib presence
            raise ValueError(f"Input validation failed: {e}")


tools_registry = ToolsRegistry()

