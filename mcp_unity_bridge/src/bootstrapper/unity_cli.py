from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional


class UnityHubCLI:
    """
    Minimal wrapper around Unity Hub CLI. If the Hub path is not available,
    methods gracefully degrade to simulated behavior to allow offline flows.
    """

    def __init__(self, unity_hub_path: Optional[str] = None):
        self.unity_hub_path = unity_hub_path or os.environ.get("UNITY_HUB_CLI")

    def _has_hub(self) -> bool:
        return bool(self.unity_hub_path and Path(self.unity_hub_path).exists())

    def list_unity_versions(self) -> List[str]:
        if not self._has_hub():
            return []
        try:
            # Example: Unity Hub -- --headless editors -i
            result = subprocess.run(
                [self.unity_hub_path, "--", "--headless", "editors", "-i"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            versions: List[str] = []
            for line in result.stdout.splitlines():
                line = line.strip()
                if line and any(ch.isdigit() for ch in line):
                    versions.append(line.split()[0])
            return versions
        except Exception:
            return []

    def create_project(self, name: str, path: str, version: Optional[str], template: Optional[str]) -> Path:
        target = Path(path).expanduser().resolve()
        target.mkdir(parents=True, exist_ok=True)
        project_path = target / name
        if self._has_hub():
            args = [
                self.unity_hub_path,
                "--",
                "--headless",
                "projects",
                "create",
                "-n",
                name,
                "-p",
                str(project_path),
            ]
            if version:
                args += ["-e", version]
            if template:
                args += ["-t", template]
            # Simple retry for flaky hub invocations
            for _ in range(3):
                result = subprocess.run(args, check=False)
                if result.returncode == 0:
                    break
        else:
            # Simulate minimal Unity project structure
            (project_path / "Assets").mkdir(parents=True, exist_ok=True)
            (project_path / "ProjectSettings").mkdir(parents=True, exist_ok=True)
            (project_path / "Packages").mkdir(parents=True, exist_ok=True)
            (project_path / "Packages" / "manifest.json").write_text(
                '{"dependencies":{}}', encoding="utf-8"
            )
        return project_path

    def add_packages(self, project_path: str | Path, packages: List[str]) -> None:
        manifest = Path(project_path) / "Packages" / "manifest.json"
        # Very light JSON editing without external deps
        import json

        manifest.parent.mkdir(parents=True, exist_ok=True)
        data = {"dependencies": {}}
        if manifest.exists():
            try:
                data = json.loads(manifest.read_text(encoding="utf-8") or "{}")
            except Exception:
                data = {"dependencies": {}}
        deps = data.setdefault("dependencies", {})
        for p in packages:
            deps.setdefault(p, "latest")
        manifest.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def import_assets(self, project_path: str | Path, assets: List[str]) -> None:
        assets_dir = Path(project_path) / "Assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        for src in assets:
            s = Path(src)
            if s.exists():
                dst = assets_dir / s.name
                if s.is_dir():
                    if dst.exists():
                        shutil.rmtree(dst)
                    shutil.copytree(s, dst)
                else:
                    shutil.copy2(s, dst)

    def compile_scripts(self, project_path: str | Path) -> None:
        # In headless environments we skip. Unity would compile on open.
        return

    def run_tests(self, project_path: str | Path) -> None:
        # Stub: integrate Unity Test Runner if Hub/Editor available.
        return
