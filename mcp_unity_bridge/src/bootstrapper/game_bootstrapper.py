from __future__ import annotations

import asyncio
import contextlib
import logging
import shutil
from pathlib import Path
from typing import Optional

from .models import GameSpecification, ProgressTracker
from .spec_parser import SpecificationParser
from .unity_cli import UnityHubCLI
from .project_structure import ProjectStructureGenerator
from ..templates.template_engine import TemplateEngine


logger = logging.getLogger(__name__)


class GameBootstrapper:
    def __init__(self, unity_hub_path: Optional[str] = None, progress: Optional[ProgressTracker] = None):
        self.unity_cli = UnityHubCLI(unity_hub_path)
        self.template_engine = TemplateEngine()
        self.code_generator = None  # Reserved for codegen integrations
        self.structure_gen = ProjectStructureGenerator()
        self.parser = SpecificationParser()
        self.progress = progress or ProgressTracker()

    async def create_game(self, specification: GameSpecification | str) -> Path:
        steps = [
            "parse-spec" if isinstance(specification, str) else "validate-spec",
            "validate-unity",
            "create-project",
            "generate-code",
            "configure-mcp",
            "create-assets",
            "setup-scene",
            "post-hooks",
        ]
        self.progress.on_start(len(steps))
        completed = 0

        def bump(step_name: str):
            nonlocal completed
            completed += 1
            self.progress.on_step_complete(step_name, completed / len(steps))

        rollback_paths: list[Path] = []

        try:
            if isinstance(specification, str):
                spec = self.parse_game_prompt(specification)
                bump("parse-spec")
            else:
                spec = specification
                self.validate_specification(spec)
                bump("validate-spec")

            # Validate Unity installation (non-fatal if running in simulated mode)
            _ = self.unity_cli.list_unity_versions()  # Probes availability
            bump("validate-unity")

            output_dir = Path(spec.output_path or ".").resolve()
            project_path = self.unity_cli.create_project(
                name=spec.name,
                path=str(output_dir),
                version=spec.unity_version or None,
                template=spec.template or None,
            )
            rollback_paths.append(project_path)
            bump("create-project")

            # Generate project structure and baseline
            self.structure_gen.create_directory_structure(project_path, spec.type)
            self.unity_cli.add_packages(project_path, spec.packages)
            self.structure_gen.generate_assembly_definitions(project_path)
            bump("generate-code")

            # Apply template if available based on spec
            tname = spec.template or self._infer_template_name(spec)
            try:
                tmpl = self.template_engine.load_template(tname)
                errs = self.template_engine.validate_template(tmpl)
                if not errs:
                    self.template_engine.apply_template(tmpl, str(project_path))
            except Exception:
                logger.info("No matching template '%s' applied (optional)", tname)

            # Configure MCP integration (drop an Editor script stub if not present)
            self._ensure_mcp_autoinstaller(project_path)
            bump("configure-mcp")

            # Copy starter assets (blueprints, etc.)
            self.structure_gen.copy_template_files(spec.template, project_path)
            bump("create-assets")

            # Scene setup placeholder (Unity will finalize on first open)
            bump("setup-scene")

            # Post creation hooks
            self.structure_gen.setup_git_repository(project_path)
            bump("post-hooks")

            self.progress.on_complete(str(project_path))
            return project_path
        except Exception as e:  # Rollback on error
            logger.exception("Bootstrap failed: %s", e)
            self.progress.on_error(e, recoverable=False)
            with contextlib.suppress(Exception):
                for p in rollback_paths:
                    if p.exists():
                        shutil.rmtree(p)
            raise

    def parse_game_prompt(self, prompt: str) -> GameSpecification:
        return self.parser.parse(prompt)

    def validate_specification(self, spec: GameSpecification) -> None:
        if not spec.name:
            raise ValueError("Specification must include a name")
        if spec.type not in ("2D", "3D", "VR", "AR"):
            raise ValueError("Invalid game type")

    def estimate_creation_time(self, spec: GameSpecification) -> float:
        base = 0.5  # hours for skeleton
        scope_factor = {"prototype": 1.0, "mvp": 2.0, "full": 4.0}.get(spec.estimated_scope, 1.0)
        mechanics_factor = 0.25 * max(1, len(spec.mechanics))
        return base + scope_factor * mechanics_factor

    def _ensure_mcp_autoinstaller(self, project_path: Path) -> None:
        # If the repo contains Editor/MCP scripts, copy the auto-installer stub into the project.
        # Otherwise, rely on the copy that exists in unity_project/ (reference)
        editor_dir = project_path / "Assets" / "Editor" / "MCP"
        editor_dir.mkdir(parents=True, exist_ok=True)
        target = editor_dir / "MCPAutoInstaller.cs"
        if not target.exists():
            target.write_text(
                """
using UnityEditor;

[InitializeOnLoad]
public class MCPAutoInstaller {
    static MCPAutoInstaller() {
        if (!IsMCPInstalled()) {
            InstallMCPBridge();
            ConfigureProjectSettings();
            StartMCPServer();
        }
    }

    static bool IsMCPInstalled() { return true; }
    static void InstallMCPBridge() {}
    static void ConfigureProjectSettings() {}
    static void StartMCPServer() {}
}
""",
                encoding="utf-8",
            )

    def _infer_template_name(self, spec: GameSpecification) -> str:
        g = (spec.genre or "").lower()
        if "platform" in g:
            return "2d_platformer" if spec.type == "2D" else "3d_platformer"
        if "fps" in g or "shooter" in g:
            return "3d_fps"
        if "rpg" in g:
            return "rpg_template"
        if "puzzle" in g:
            return "puzzle_game"
        return "2d_platformer" if spec.type == "2D" else "3d_fps"
