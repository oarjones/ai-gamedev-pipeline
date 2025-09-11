"""Adapter registry to instantiate adapters by name and per-project mapping."""

from __future__ import annotations

from typing import Dict

from .base import AgentAdapter
from .cli_generic import CLIGenericAdapter


_REGISTRY: Dict[str, type[AgentAdapter]] = {
    CLIGenericAdapter.name: CLIGenericAdapter,
}


def get_adapter(name: str | None) -> AgentAdapter:
    if not name:
      return CLIGenericAdapter()
    cls = _REGISTRY.get(name) or CLIGenericAdapter
    return cls()

