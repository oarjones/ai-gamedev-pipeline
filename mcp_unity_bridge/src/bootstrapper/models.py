from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Literal, Optional


Scope = Literal["prototype", "mvp", "full"]
GameType = Literal["2D", "3D", "VR", "AR"]


@dataclass
class GameMechanic:
    name: str
    description: str = ""


@dataclass
class GameSpecification:
    name: str
    type: GameType
    genre: str
    platform: List[str] = field(default_factory=list)
    unity_version: str = ""
    packages: List[str] = field(default_factory=list)
    mechanics: List[GameMechanic] = field(default_factory=list)
    art_style: str = ""
    target_audience: str = ""
    estimated_scope: Scope = "prototype"
    template: Optional[str] = None
    output_path: Optional[str] = None


class ProgressTracker:
    """Simple callback-based progress tracker interface with safe no-ops."""

    def on_start(self, total_steps: int) -> None:  # pragma: no cover - interface
        pass

    def on_step_complete(self, step_name: str, progress: float) -> None:  # pragma: no cover - interface
        pass

    def on_error(self, error: Exception, recoverable: bool) -> None:  # pragma: no cover - interface
        pass

    def on_complete(self, project_path: str) -> None:  # pragma: no cover - interface
        pass

