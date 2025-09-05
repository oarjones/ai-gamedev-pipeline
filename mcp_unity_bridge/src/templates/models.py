from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any


@dataclass
class TemplateParameter:
    name: str
    type: str
    default: Any = None
    description: str = ""


@dataclass
class ScriptSpec:
    src: str
    target: str
    parameters: List[str] = field(default_factory=list)


@dataclass
class SceneSpec:
    name: str
    is_default: bool = False


@dataclass
class PostInstallSpec:
    script: str


@dataclass
class TemplateInfo:
    id: str
    name: str
    version: str
    description: str = ""
    unity_version: str = ""
    path: Optional[Path] = None


@dataclass
class GameTemplate:
    info: TemplateInfo
    dependencies: Dict[str, str] = field(default_factory=dict)  # package -> version
    parameters: List[TemplateParameter] = field(default_factory=list)
    scripts: List[ScriptSpec] = field(default_factory=list)
    scenes: List[SceneSpec] = field(default_factory=list)
    post_install: List[PostInstallSpec] = field(default_factory=list)
    root: Optional[Path] = None


@dataclass
class ValidationError:
    message: str
    field: Optional[str] = None

