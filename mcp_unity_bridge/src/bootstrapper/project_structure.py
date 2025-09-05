from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional


class ProjectStructureGenerator:
    def create_directory_structure(self, base_path: str | Path, game_type: str) -> None:
        base = Path(base_path)
        for p in [
            base / "Assets",
            base / "Assets" / "Scripts",
            base / "Assets" / "Scenes",
            base / "Assets" / "Textures" / "Blueprints",
            base / "Assets" / "Editor",
            base / "Packages",
            base / "ProjectSettings",
        ]:
            p.mkdir(parents=True, exist_ok=True)

        # Minimal scene placeholder
        (base / "Assets" / "Scenes" / "Main.unity").touch(exist_ok=True)

    def copy_template_files(self, template_name: Optional[str], target_path: str | Path) -> None:
        # Copy available blueprint reference images, if present in repo templates/
        repo_templates = Path("templates")
        target = Path(target_path) / "Assets" / "Textures" / "Blueprints"
        target.mkdir(parents=True, exist_ok=True)
        for name in ["front.png", "left.png", "top.png"]:
            src = repo_templates / name
            if src.exists():
                shutil.copy2(src, target / name)

    def generate_assembly_definitions(self, base_path: str | Path) -> None:
        asm = {
            "name": "Game.Scripts",
            "references": [],
            "includePlatforms": [],
            "excludePlatforms": [],
            "allowUnsafeCode": False,
            "overrideReferences": False,
            "precompiledReferences": [],
            "autoReferenced": True,
            "defineConstraints": [],
            "versionDefines": [],
            "noEngineReferences": False,
        }
        path = Path(base_path) / "Assets" / "Scripts" / "Game.Scripts.asmdef"
        path.write_text(json.dumps(asm, indent=2), encoding="utf-8")

    def create_folder_meta_files(self, base_path: str | Path) -> None:
        # Unity will auto-generate .meta files; creating placeholders is optional.
        # We skip heavy meta generation to avoid incorrect GUIDs.
        return

    def setup_git_repository(self, path: str | Path, gitignore_template: Optional[str] = None) -> None:
        p = Path(path)
        try:
            subprocess.run(["git", "init", str(p)], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except Exception:
            pass
        gitignore = p / ".gitignore"
        if gitignore_template and Path(gitignore_template).exists():
            shutil.copy2(gitignore_template, gitignore)
        elif not gitignore.exists():
            gitignore.write_text(
                """# Unity
Library/
Temp/
Obj/
Build/
Builds/
Logs/
UserSettings/
.vs/
.idea/
*.csproj
*.sln
*.user
*.tmp
""",
                encoding="utf-8",
            )

