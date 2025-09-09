from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional

from .models import (
    GameTemplate,
    TemplateInfo,
    TemplateParameter,
    ScriptSpec,
    SceneSpec,
    PostInstallSpec,
    ValidationError,
)


class TemplateEngine:
    def __init__(self, templates_root: Optional[str] = None):
        self.templates_root = Path(templates_root or "templates").resolve()

    # ---- Discovery ----
    def list_available_templates(self) -> List[TemplateInfo]:
        infos: List[TemplateInfo] = []
        if not self.templates_root.exists():
            return infos
        for d in self.templates_root.iterdir():
            if not d.is_dir():
                continue
            manifest = d / "manifest.yaml"
            if manifest.exists():
                try:
                    data = self._load_manifest(manifest)
                    infos.append(
                        TemplateInfo(
                            id=d.name,
                            name=str(data.get("name", d.name)),
                            version=str(data.get("version", "0.0.0")),
                            description=str(data.get("description", "")),
                            unity_version=str(data.get("unity_version", "")),
                            path=d,
                        )
                    )
                except Exception:
                    # Skip invalid manifests
                    continue
        return infos

    def load_template(self, name: str) -> GameTemplate:
        folder = self.templates_root / name
        manifest = folder / "manifest.yaml"
        if not manifest.exists():
            raise FileNotFoundError(f"Template '{name}' not found at {manifest}")
        data = self._load_manifest(manifest)

        deps = {}
        for pkg in data.get("dependencies", {}).get("packages", []):
            if isinstance(pkg, str):
                deps[pkg] = "latest"
            elif isinstance(pkg, dict):
                for k, v in pkg.items():
                    deps[str(k)] = str(v)

        params = [
            TemplateParameter(
                name=str(p.get("name")),
                type=str(p.get("type", "string")),
                default=p.get("default"),
                description=str(p.get("description", "")),
            )
            for p in data.get("parameters", [])
            if isinstance(p, dict) and p.get("name")
        ]

        scripts = [
            ScriptSpec(
                src=str(s.get("src")),
                target=str(s.get("target", "Assets/Scripts/")),
                parameters=[str(x) for x in (s.get("parameters") or [])],
            )
            for s in data.get("scripts", [])
            if isinstance(s, dict) and s.get("src")
        ]

        scenes = [
            SceneSpec(name=str(s.get("name")), is_default=bool(s.get("is_default", False)))
            for s in data.get("scenes", [])
            if isinstance(s, dict) and s.get("name")
        ]

        post_install = [
            PostInstallSpec(script=str(s.get("script")))
            for s in data.get("post_install", [])
            if isinstance(s, dict) and s.get("script")
        ]

        info = TemplateInfo(
            id=folder.name,
            name=str(data.get("name", folder.name)),
            version=str(data.get("version", "0.0.0")),
            description=str(data.get("description", "")),
            unity_version=str(data.get("unity_version", "")),
            path=folder,
        )

        return GameTemplate(
            info=info,
            dependencies=deps,
            parameters=params,
            scripts=scripts,
            scenes=scenes,
            post_install=post_install,
            root=folder,
        )

    # ---- Validation ----
    def validate_template(self, template: GameTemplate) -> List[ValidationError]:
        errors: List[ValidationError] = []
        if not template.info.name:
            errors.append(ValidationError("Template missing name", field="name"))
        if not template.info.version:
            errors.append(ValidationError("Template missing version", field="version"))
        for s in template.scripts:
            if not (template.root / "scripts" / s.src).exists():
                errors.append(ValidationError(f"Missing script file: {s.src}", field="scripts"))
        return errors

    # ---- Application ----
    def apply_template(self, template: GameTemplate, project_path: str, parameters: Optional[Dict[str, str]] = None) -> None:
        project = Path(project_path)
        project.mkdir(parents=True, exist_ok=True)

        # 1) Packages
        self._add_packages(project, template.dependencies)

        # 2) Scripts (copy with param substitution)
        params = {p.name: p.default for p in template.parameters}
        if parameters:
            params.update(parameters)
        for spec in template.scripts:
            src = template.root / "scripts" / spec.src
            dst_dir = project / spec.target
            dst_dir.mkdir(parents=True, exist_ok=True)
            content = src.read_text(encoding="utf-8") if src.exists() else ""
            content = self._apply_parameters(content, {k: params.get(k) for k in spec.parameters})
            (dst_dir / Path(spec.src).name).write_text(content, encoding="utf-8")

        # 3) Scenes (placeholder creation)
        scenes_dir = project / "Assets" / "Scenes"
        scenes_dir.mkdir(parents=True, exist_ok=True)
        for scene in template.scenes:
            (scenes_dir / f"{scene.name}.unity").touch(exist_ok=True)

        # 4) Post-install scripts: copy into Editor for later execution by user
        editor_dir = project / "Assets" / "Editor" / "TemplatePostInstall"
        for pi in template.post_install:
            src = template.root / "scripts" / pi.script
            if src.exists():
                editor_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, editor_dir / Path(pi.script).name)

    def merge_templates(self, template_a: GameTemplate, template_b: GameTemplate) -> GameTemplate:
        deps = dict(template_a.dependencies)
        deps.update(template_b.dependencies)
        # Merge parameters by name, template_b overrides defaults
        param_map = {p.name: p for p in template_a.parameters}
        for p in template_b.parameters:
            param_map[p.name] = p
        scripts = template_a.scripts + template_b.scripts
        scenes = template_a.scenes + template_b.scenes
        post = template_a.post_install + template_b.post_install
        info = TemplateInfo(
            id=f"{template_a.info.id}+{template_b.info.id}",
            name=f"{template_a.info.name} + {template_b.info.name}",
            version=f"{template_a.info.version}+{template_b.info.version}",
            description=f"Merged: {template_a.info.description} | {template_b.info.description}",
            unity_version=template_a.info.unity_version or template_b.info.unity_version,
            path=None,
        )
        return GameTemplate(
            info=info,
            dependencies=deps,
            parameters=list(param_map.values()),
            scripts=scripts,
            scenes=scenes,
            post_install=post,
            root=None,
        )

    # ---- Creation ----
    def create_custom_template(self, base_template: str, modifications: dict) -> GameTemplate:
        base = self.load_template(base_template)
        # Apply modifications only to known fields
        deps = dict(base.dependencies)
        deps.update(modifications.get("dependencies", {}))

        param_overrides = {p["name"]: p for p in modifications.get("parameters", []) if "name" in p}
        params: List[TemplateParameter] = []
        for p in base.parameters:
            if p.name in param_overrides:
                ov = param_overrides[p.name]
                params.append(
                    TemplateParameter(
                        name=p.name,
                        type=str(ov.get("type", p.type)),
                        default=ov.get("default", p.default),
                        description=str(ov.get("description", p.description)),
                    )
                )
            else:
                params.append(p)

        info = TemplateInfo(
            id=f"custom-{base.info.id}",
            name=modifications.get("name", base.info.name + " (Custom)"),
            version=str(modifications.get("version", base.info.version)),
            description=str(modifications.get("description", base.info.description)),
            unity_version=str(modifications.get("unity_version", base.info.unity_version)),
            path=base.info.path,
        )

        return GameTemplate(
            info=info,
            dependencies=deps,
            parameters=params,
            scripts=base.scripts,
            scenes=base.scenes,
            post_install=base.post_install,
            root=base.root,
        )

    # ---- Helpers ----
    def _load_manifest(self, path: Path) -> dict:
        text = path.read_text(encoding="utf-8").strip()
        # YAML 1.2 is a superset of JSON, accept JSON manifests for simplicity
        if text.startswith("{"):
            return json.loads(text)
        # Fallback: extremely naive YAML to dict for simple key/values and lists we control
        # Recommend keeping manifests as JSON for reliability.
        data: Dict[str, any] = {}
        current_key: Optional[str] = None
        list_acc: Optional[List] = None
        for raw in text.splitlines():
            line = raw.rstrip()
            if not line or line.lstrip().startswith("#"):
                continue
            if not line.startswith(" ") and ":" in line:
                key, val = [x.strip() for x in line.split(":", 1)]
                if val == "" or val == "|" or val == ">":
                    current_key = key
                    list_acc = None
                    data[current_key] = []
                else:
                    data[key] = val.strip('"')
                    current_key = key
                    list_acc = None
            elif line.lstrip().startswith("-"):
                item = line.lstrip()[1:].strip()
                if current_key and isinstance(data.get(current_key), list):
                    # Try to parse mapping like "key: value" inside list
                    if ":" in item:
                        k, v = [x.strip() for x in item.split(":", 1)]
                        data[current_key].append({k: v.strip('"')})
                    else:
                        data[current_key].append(item.strip('"'))
        return data

    def _apply_parameters(self, content: str, parameters: Dict[str, object]) -> str:
        if not parameters:
            return content
        def repl(match):
            key = match.group(1)
            val = parameters.get(key)
            return str(val) if val is not None else match.group(0)
        return re.sub(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}", repl, content)

    def _add_packages(self, project: Path, packages: Dict[str, str]) -> None:
        manifest = project / "Packages" / "manifest.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        data = {"dependencies": {}}
        if manifest.exists():
            try:
                data = json.loads(manifest.read_text(encoding="utf-8") or "{}")
            except Exception:
                data = {"dependencies": {}}
        deps = data.setdefault("dependencies", {})
        for pkg, ver in packages.items():
            deps[pkg] = ver or "latest"
        manifest.write_text(json.dumps(data, indent=2), encoding="utf-8")

