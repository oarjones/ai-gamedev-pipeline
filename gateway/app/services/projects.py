"""Project management service layer with Unity project support."""

import json
import os
import re
import subprocess
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional
import logging

from app.db import DatabaseManager, ProjectDB, db
from app.models.core import CreateProject, Project

logger = logging.getLogger(__name__)


class ProjectService:
    """Service for managing projects with filesystem and database operations."""
    
    def __init__(self, projects_root: str = "projects", db_instance: Optional[DatabaseManager] = None) -> None:
        """Initialize project service.
        
        Args:
            projects_root: Root directory for all projects
            db_instance: Database instance to use (defaults to global db)
        """
        self.projects_root = Path(projects_root)
        self.projects_root.mkdir(exist_ok=True)
        self.db = db_instance or db
    
    def _sanitize_name(self, name: str) -> str:
        """Sanitize project name to create valid directory name.
        
        Args:
            name: Original project name
            
        Returns:
            Sanitized name containing only [a-z0-9-]
        """
        # Convert to lowercase and replace spaces/underscores with hyphens
        sanitized = re.sub(r'[_\s]+', '-', name.lower())
        # Remove all non-alphanumeric characters except hyphens
        sanitized = re.sub(r'[^a-z0-9-]', '', sanitized)
        # Remove leading/trailing hyphens and collapse multiple hyphens
        sanitized = re.sub(r'-+', '-', sanitized).strip('-')
        
        if not sanitized:
            raise ValueError("Project name must contain at least one alphanumeric character")
        
        return sanitized
    
    def _generate_project_id(self, name: str) -> str:
        """Generate unique project ID from name.
        
        Args:
            name: Project name
            
        Returns:
            Unique project ID
        """
        base_id = self._sanitize_name(name)
        
        # Check if this ID already exists
        if not self.db.get_project(base_id):
            return base_id
        
        # If it exists, append a number
        counter = 1
        while True:
            candidate_id = f"{base_id}-{counter}"
            if not self.db.get_project(candidate_id):
                return candidate_id
            counter += 1
    
    def _create_unity_project_structure(self, project_dir: Path) -> None:
        """Create Unity-specific project structure.
        
        Args:
            project_dir: Path to project directory
        """
        logger.info(f"Creating Unity project structure in {project_dir}")
        
        # Essential Unity directories
        unity_dirs = [
            "Assets",
            "Assets/Scripts",
            "Assets/Materials",
            "Assets/Textures",
            "Assets/Prefabs",
            "Assets/Scenes",
            "Assets/Editor",
            "Assets/Editor/MCP",  # Para los scripts del puente MCP
            "Assets/Generated",    # Para assets generados por Blender
            "ProjectSettings",
            "Packages",
            "UserSettings",
        ]
        
        for dir_name in unity_dirs:
            (project_dir / dir_name).mkdir(parents=True, exist_ok=True)

        # Copy essential template content from repo unity_project
        try:
            repo_root = Path(__file__).resolve().parents[3]
            tpl_root = repo_root / "unity_project"
            # 1) Packages (manifest + lock) to ensure required modules
            tpl_packages = tpl_root / "Packages"
            dst_packages = project_dir / "Packages"
            if tpl_packages.exists():
                for name in ("manifest.json", "packages-lock.json"):
                    src = tpl_packages / name
                    if src.exists():
                        dst = dst_packages / name
                        try:
                            shutil.copy2(src, dst)
                            logger.info("Copied package file: %s", dst)
                        except Exception as e:
                            logger.warning("Failed to copy package file %s: %s", src, e)
            # 2) Assets/Plugins (e.g., websocket-sharp.dll)
            tpl_plugins = tpl_root / "Assets" / "Plugins"
            dst_plugins = project_dir / "Assets" / "Plugins"
            if tpl_plugins.exists():
                try:
                    shutil.copytree(tpl_plugins, dst_plugins, dirsExist_ok=True if hasattr(shutil, 'dirsExist_ok') else True)
                except TypeError:
                    # Python <3.8 compatibility fallback
                    shutil.copytree(tpl_plugins, dst_plugins, dirs_exist_ok=True)
                except Exception as e:
                    logger.warning("Failed to copy Plugins from template: %s", e)
        except Exception as e:
            logger.warning("Template copy step failed: %s", e)
        
        # Crear un archivo de escena vacío básico
        main_scene = project_dir / "Assets" / "Scenes" / "Main.unity"
        if not main_scene.exists():
            # Escena Unity mínima válida
            scene_content = """%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!29 &1
OcclusionCullingSettings:
  m_ObjectHideFlags: 0
  serializedVersion: 2
  m_OcclusionBakeSettings:
    smallestOccluder: 5
    smallestHole: 0.25
    backfaceThreshold: 100
  m_SceneGUID: 00000000000000000000000000000000
  m_OcclusionCullingData: {fileID: 0}
--- !u!104 &2
RenderSettings:
  m_ObjectHideFlags: 0
  serializedVersion: 9
  m_Fog: 0
  m_FogColor: {r: 0.5, g: 0.5, b: 0.5, a: 1}
  m_FogMode: 3
  m_FogDensity: 0.01
  m_LinearFogStart: 0
  m_LinearFogEnd: 300
  m_AmbientSkyColor: {r: 0.212, g: 0.227, b: 0.259, a: 1}
  m_AmbientEquatorColor: {r: 0.114, g: 0.125, b: 0.133, a: 1}
  m_AmbientGroundColor: {r: 0.047, g: 0.043, b: 0.035, a: 1}
  m_AmbientIntensity: 1
  m_AmbientMode: 0
  m_SubtractiveShadowColor: {r: 0.42, g: 0.478, b: 0.627, a: 1}
  m_SkyboxMaterial: {fileID: 10304, guid: 0000000000000000f000000000000000, type: 0}
  m_HaloStrength: 0.5
  m_FlareStrength: 1
  m_FlareFadeSpeed: 3
  m_HaloTexture: {fileID: 0}
  m_SpotCookie: {fileID: 10001, guid: 0000000000000000e000000000000000, type: 0}
  m_DefaultReflectionMode: 0
  m_DefaultReflectionResolution: 128
  m_ReflectionBounces: 1
  m_ReflectionIntensity: 1
  m_CustomReflection: {fileID: 0}
  m_Sun: {fileID: 0}
  m_IndirectSpecularColor: {r: 0, g: 0, b: 0, a: 1}
  m_UseRadianceAmbientProbe: 0
--- !u!157 &3
LightmapSettings:
  m_ObjectHideFlags: 0
  serializedVersion: 12
  m_GIWorkflowMode: 1
  m_GISettings:
    serializedVersion: 2
    m_BounceScale: 1
    m_IndirectOutputScale: 1
    m_AlbedoBoost: 1
    m_EnvironmentLightingMode: 0
    m_EnableBakedLightmaps: 1
    m_EnableRealtimeLightmaps: 0
  m_LightmapEditorSettings:
    serializedVersion: 12
    m_Resolution: 2
    m_BakeResolution: 40
    m_AtlasSize: 1024
    m_AO: 0
    m_AOMaxDistance: 1
    m_CompAOExponent: 1
    m_CompAOExponentDirect: 0
    m_ExtractAmbientOcclusion: 0
    m_Padding: 2
    m_LightmapParameters: {fileID: 0}
    m_LightmapsBakeMode: 1
    m_TextureCompression: 1
    m_FinalGather: 0
    m_FinalGatherFiltering: 1
    m_FinalGatherRayCount: 256
    m_ReflectionCompression: 2
    m_MixedBakeMode: 2
    m_BakeBackend: 1
    m_PVRSampling: 1
    m_PVRDirectSampleCount: 32
    m_PVRSampleCount: 512
    m_PVRBounces: 2
    m_PVREnvironmentSampleCount: 256
    m_PVREnvironmentReferencePointCount: 2048
    m_PVRFilteringMode: 1
    m_PVRDenoiserTypeDirect: 1
    m_PVRDenoiserTypeIndirect: 1
    m_PVRDenoiserTypeAO: 1
    m_PVRFilterTypeDirect: 0
    m_PVRFilterTypeIndirect: 0
    m_PVRFilterTypeAO: 0
    m_PVREnvironmentMIS: 1
    m_PVRCulling: 1
    m_PVRFilteringGaussRadiusDirect: 1
    m_PVRFilteringGaussRadiusIndirect: 5
    m_PVRFilteringGaussRadiusAO: 2
    m_PVRFilteringAtrousPositionSigmaDirect: 0.5
    m_PVRFilteringAtrousPositionSigmaIndirect: 2
    m_PVRFilteringAtrousPositionSigmaAO: 1
    m_ExportTrainingData: 0
    m_TrainingDataDestination: TrainingData
    m_LightProbeSampleCountMultiplier: 4
  m_LightingDataAsset: {fileID: 0}
  m_LightingSettings: {fileID: 0}
--- !u!196 &4
NavMeshSettings:
  serializedVersion: 2
  m_ObjectHideFlags: 0
  m_BuildSettings:
    serializedVersion: 2
    agentTypeID: 0
    agentRadius: 0.5
    agentHeight: 2
    agentSlope: 45
    agentClimb: 0.4
    ledgeDropHeight: 0
    maxJumpAcrossDistance: 0
    minRegionArea: 2
    manualCellSize: 0
    cellSize: 0.16666667
    manualTileSize: 0
    tileSize: 256
    accuratePlacement: 0
    maxJobWorkers: 0
    preserveTilesOutsideBounds: 0
    debug:
      m_Flags: 0
  m_NavMeshData: {fileID: 0}
--- !u!1 &705507993
GameObject:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {fileID: 0}
  m_PrefabInstance: {fileID: 0}
  m_PrefabAsset: {fileID: 0}
  serializedVersion: 6
  m_Component:
  - component: {fileID: 705507995}
  - component: {fileID: 705507994}
  m_Layer: 0
  m_Name: Directional Light
  m_TagString: Untagged
  m_Icon: {fileID: 0}
  m_NavMeshLayer: 0
  m_StaticEditorFlags: 0
  m_IsActive: 1
--- !u!108 &705507994
Light:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {fileID: 0}
  m_PrefabInstance: {fileID: 0}
  m_PrefabAsset: {fileID: 0}
  m_GameObject: {fileID: 705507993}
  m_Enabled: 1
  serializedVersion: 10
  m_Type: 1
  m_Shape: 0
  m_Color: {r: 1, g: 0.95686275, b: 0.8392157, a: 1}
  m_Intensity: 1
  m_Range: 10
  m_SpotAngle: 30
  m_InnerSpotAngle: 21.80208
  m_CookieSize: 10
  m_Shadows:
    m_Type: 2
    m_Resolution: -1
    m_CustomResolution: -1
    m_Strength: 1
    m_Bias: 0.05
    m_NormalBias: 0.4
    m_NearPlane: 0.2
    m_CullingMatrixOverride:
      e00: 1
      e01: 0
      e02: 0
      e03: 0
      e10: 0
      e11: 1
      e12: 0
      e13: 0
      e20: 0
      e21: 0
      e22: 1
      e23: 0
      e30: 0
      e31: 0
      e32: 0
      e33: 1
    m_UseCullingMatrixOverride: 0
  m_Cookie: {fileID: 0}
  m_DrawHalo: 0
  m_Flare: {fileID: 0}
  m_RenderMode: 0
  m_CullingMask:
    serializedVersion: 2
    m_Bits: 4294967295
  m_RenderingLayerMask: 1
  m_Lightmapping: 4
  m_LightShadowCasterMode: 0
  m_AreaSize: {x: 1, y: 1}
  m_BounceIntensity: 1
  m_ColorTemperature: 6570
  m_UseColorTemperature: 0
  m_BoundingSphereOverride: {x: 0, y: 0, z: 0, w: 0}
  m_UseBoundingSphereOverride: 0
  m_UseViewFrustumForShadowCasterCull: 1
  m_ShadowRadius: 0
  m_ShadowAngle: 0
--- !u!4 &705507995
Transform:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {fileID: 0}
  m_PrefabInstance: {fileID: 0}
  m_PrefabAsset: {fileID: 0}
  m_GameObject: {fileID: 705507993}
  m_LocalRotation: {x: 0.40821788, y: -0.23456968, z: 0.10938163, w: 0.8754261}
  m_LocalPosition: {x: 0, y: 3, z: 0}
  m_LocalScale: {x: 1, y: 1, z: 1}
  m_Children: []
  m_Father: {fileID: 0}
  m_RootOrder: 1
  m_LocalEulerAnglesHint: {x: 50, y: -30, z: 0}
"""
            main_scene.write_text(scene_content, encoding="utf-8")
        
        # Copiar los scripts del puente MCP a la carpeta del Editor
        self._copy_mcp_scripts(project_dir)

        # Copiar solución mínima de Editor para mejorar soporte IDE
        self._copy_unity_editor_csproj(project_dir)

        # Copiar csproj de runtime principal para IntelliSense en scripts de juego
        self._copy_unity_runtime_csproj(project_dir)
        
        # Crear archivo .gitignore para Unity
        gitignore = project_dir / ".gitignore"
        if not gitignore.exists():
            gitignore_content = """# Unity
[Ll]ibrary/
[Tt]emp/
[Oo]bj/
[Bb]uild/
[Bb]uilds/
[Ll]ogs/
[Uu]ser[Ss]ettings/
[Mm]emory[Cc]aptures/

# Visual Studio / Rider
.vs/
.idea/
*.csproj
*.sln
*.suo
*.tmp
*.user
*.userprefs
*.pidb
*.booproj
*.svd
*.pdb
*.mdb
*.opendb
*.VC.db

# Unity3D generated meta files
*.pidb.meta
*.pdb.meta
*.mdb.meta

# Unity3D Generated File On Crash Reports
sysinfo.txt

# Builds
*.apk
*.unitypackage
"""
            gitignore.write_text(gitignore_content, encoding="utf-8")

        # Crear script para lanzar el agente Gemini CLI desde la raíz del proyecto
        try:
            bat_path = project_dir.parent if (project_dir.name.lower() == "unity_project") else project_dir
            bat_file = bat_path / "start_gemini_cli.bat"
            if not bat_file.exists():
                bat_content = (
                    "@echo off\r\n"
                    "setlocal ENABLEEXTENSIONS\r\n"
                    "cd /d \"%~dp0\"\r\n"
                    "echo ===========================================\r\n"
                    "echo    Gemini CLI - Project Workspace Console\r\n"
                    "echo ===========================================\r\n"
                    "REM Asegurar rutas de npm (global y local del proyecto)\r\n"
                    "set \"PATH=%APPDATA%\\npm;%PATH%\"\r\n"
                    "if exist \"%~dp0node_modules\\.bin\" set \"PATH=%~dp0node_modules\\.bin;%PATH%\"\r\n"
                    "echo Working dir: %CD%\r\n"
                    "if \"%GEMINI_API_KEY%\"==\"\" echo [WARN] GEMINI_API_KEY is not set.\r\n"
                    "echo.\r\n"
                    "REM Pasa argumentos opcionales al CLI\r\n"
                    "gemini %*\r\n"
                    "echo.\r\n"
                    "echo [Session ended]\r\n"
                    "pause\r\n"
                )
                bat_file.write_text(bat_content, encoding="utf-8")
                logger.info("Created launcher: %s", bat_file)
        except Exception as e:
            logger.warning("Failed to create start_gemini_cli.bat: %s", e)
    
    def _copy_mcp_scripts(self, project_dir: Path) -> None:
        """Copy MCP-related Unity Editor scripts from template into new project.

        Copies both 'MCP' and 'MCPBridge' folders recursively from
        <repo_root>/unity_project/Assets/Editor into the project's
        Assets/Editor destination.

        Args:
            project_dir: Path to project directory
        """
        # Resolve repository root from this file location
        repo_root = Path(__file__).resolve().parents[3]
        editor_src_root = repo_root / "unity_project" / "Assets" / "Editor"
        # Support projects that have 'unity_project' subfolder
        editor_dst_root = (project_dir / "unity_project" / "Assets" / "Editor") if (project_dir / "unity_project").exists() else (project_dir / "Assets" / "Editor")

        def _copy_tree(src: Path, dst: Path) -> None:
            if not src.exists():
                logger.warning(f"MCP scripts source not found at {src}")
                return
            logger.info(f"Copying Unity Editor scripts from {src} to {dst}")
            try:
                shutil.copytree(src, dst, dirs_exist_ok=True)
            except Exception as e:
                logger.error(f"Failed to copy scripts from {src} to {dst}: {e}")

        # Copy MCP folder
        _copy_tree(editor_src_root / "MCP", editor_dst_root / "MCP")
        # Copy MCPBridge folder if present (installer, health checks, etc.)
        _copy_tree(editor_src_root / "MCPBridge", editor_dst_root / "MCPBridge")

    def _copy_unity_editor_csproj(self, project_dir: Path) -> None:
        """Copy Assembly-CSharp-Editor.csproj from template into the new project.

        This provides basic IDE project support even before Unity regenerates
        solution files.
        """
        try:
            repo_root = Path(__file__).resolve().parents[3]
            src = repo_root / "unity_project" / "Assembly-CSharp-Editor.csproj"
            dst = project_dir / "Assembly-CSharp-Editor.csproj"
            if not src.exists():
                logger.warning("Unity Editor csproj template not found at %s", src)
                return
            # Copy as-is; template is generic and uses relative paths
            shutil.copy2(src, dst)
            logger.info("Copied Unity csproj to %s", dst)
        except Exception as e:
            logger.warning("Failed to copy Unity csproj: %s", e)

    def _copy_unity_runtime_csproj(self, project_dir: Path) -> None:
        """Copy Assembly-CSharp.csproj from template into the new project.

        This mirrors the Editor csproj copy and gives IDE support for runtime scripts.
        """
        try:
            repo_root = Path(__file__).resolve().parents[3]
            src = repo_root / "unity_project" / "Assembly-CSharp.csproj"
            dst = project_dir / "Assembly-CSharp.csproj"
            if not src.exists():
                logger.warning("Unity runtime csproj template not found at %s", src)
                return
            shutil.copy2(src, dst)
            logger.info("Copied Unity runtime csproj to %s", dst)
        except Exception as e:
            logger.warning("Failed to copy Unity runtime csproj: %s", e)

    def ensure_unity_baseline(self, project_dir: Path) -> None:
        """Ensure minimal Unity project baseline from template for an existing project.

        - ProjectSettings/ProjectVersion.txt set to 6000.0.15f1 if missing/no version line
        - Copy Packages/manifest.json and packages-lock.json from template if missing
        - Copy Assets/Plugins from template (e.g., websocket-sharp.dll) if missing
        """
        try:
            # Version file
            target_version = "6000.0.15f1"
            unity_dir = project_dir / "unity_project" if (project_dir / "unity_project").exists() else project_dir
            pv = unity_dir / "ProjectSettings" / "ProjectVersion.txt"
            if not pv.exists():
                pv.parent.mkdir(parents=True, exist_ok=True)
                pv.write_text(f"m_EditorVersion: {target_version}\n", encoding="utf-8")
                logger.info("[baseline] Wrote ProjectVersion.txt with %s", target_version)
            else:
                try:
                    txt = pv.read_text(encoding="utf-8", errors="replace")
                    if "m_EditorVersion:" not in txt:
                        pv.write_text(f"m_EditorVersion: {target_version}\n", encoding="utf-8")
                        logger.info("[baseline] Updated ProjectVersion.txt with %s", target_version)
                except Exception:
                    pv.write_text(f"m_EditorVersion: {target_version}\n", encoding="utf-8")
                    logger.info("[baseline] Rewrote ProjectVersion.txt with %s", target_version)
        except Exception as e:
            logger.warning("[baseline] Version ensure failed: %s", e)

        try:
            repo_root = Path(__file__).resolve().parents[3]
            tpl_root = repo_root / "unity_project"
            unity_dir = project_dir / "unity_project" if (project_dir / "unity_project").exists() else project_dir
            # Packages files
            tpl_packages = tpl_root / "Packages"
            dst_packages = unity_dir / "Packages"
            dst_packages.mkdir(parents=True, exist_ok=True)
            for name in ("manifest.json", "packages-lock.json"):
                src = tpl_packages / name
                dst = dst_packages / name
                if src.exists() and not dst.exists():
                    try:
                        shutil.copy2(src, dst)
                        logger.info("[baseline] Copied package file: %s", dst)
                    except Exception as e:
                        logger.warning("[baseline] Copy package file failed %s: %s", src, e)
            # Ensure manifest contains Newtonsoft JSON package
            try:
                mpath = dst_packages / "manifest.json"
                import json
                if mpath.exists():
                    data = json.loads(mpath.read_text(encoding="utf-8"))
                    deps = data.get("dependencies") or {}
                    if "com.unity.nuget.newtonsoft-json" not in deps:
                        deps["com.unity.nuget.newtonsoft-json"] = "3.2.1"
                        data["dependencies"] = deps
                        mpath.write_text(json.dumps(data, indent=2), encoding="utf-8")
                        logger.info("[baseline] Added Newtonsoft JSON package to manifest.json")
            except Exception as e:
                logger.warning("[baseline] Failed to ensure Newtonsoft package: %s", e)
            # Plugins
            tpl_plugins = tpl_root / "Assets" / "Plugins"
            dst_plugins = unity_dir / "Assets" / "Plugins"
            if tpl_plugins.exists():
                try:
                    dst_plugins.mkdir(parents=True, exist_ok=True)
                    # Merge copy
                    for root, dirs, files in os.walk(tpl_plugins):
                        rel = Path(root).relative_to(tpl_plugins)
                        target_dir = dst_plugins / rel
                        target_dir.mkdir(parents=True, exist_ok=True)
                        for f in files:
                            srcf = Path(root) / f
                            dstf = target_dir / f
                            if not dstf.exists():
                                shutil.copy2(srcf, dstf)
                    logger.info("[baseline] Ensured Plugins content from template")
                except Exception as e:
                    logger.warning("[baseline] Copy Plugins failed: %s", e)
            # Editor scripts (MCP + MCPBridge)
            try:
                tpl_editor = tpl_root / "Assets" / "Editor"
                if tpl_editor.exists():
                    dst_editor = unity_dir / "Assets" / "Editor"
                    dst_editor.mkdir(parents=True, exist_ok=True)
                    for sub in ("MCP", "MCPBridge"):
                        s = tpl_editor / sub
                        if s.exists():
                            for root, dirs, files in os.walk(s):
                                rel = Path(root).relative_to(tpl_editor)
                                tdir = dst_editor / rel
                                tdir.mkdir(parents=True, exist_ok=True)
                                for f in files:
                                    srcf = Path(root) / f
                                    dstf = tdir / f
                                    if not dstf.exists():
                                        shutil.copy2(srcf, dstf)
                    logger.info("[baseline] Ensured Editor scripts from template")
            except Exception as e:
                logger.warning("[baseline] Copy Editor scripts failed: %s", e)
        except Exception as e:
            logger.warning("[baseline] Template copy failed: %s", e)
    
    def _create_project_structure(self, project_id: str, project_name: str, settings: dict = None) -> Path:
        """Create filesystem structure for a new project.
        
        Args:
            project_id: Project ID (used as directory name)
            project_name: Human-readable project name
            settings: Project settings to include in project.json
            
        Returns:
            Path to created project directory
        """
        project_dir = self.projects_root / project_id
        
        # Create main project directory
        project_dir.mkdir(exist_ok=True)
        
        # Create Unity project structure under subfolder 'unity_project'
        unity_dir = project_dir / "unity_project"
        unity_dir.mkdir(parents=True, exist_ok=True)
        self._create_unity_project_structure(unity_dir)
        # Ensure Unity Editor version to avoid mismatch prompts/reimports
        try:
            target_version = "6000.0.15f1"
            pv = project_dir / "ProjectSettings" / "ProjectVersion.txt"
            if not pv.exists():
                pv.write_text(f"m_EditorVersion: {target_version}\n", encoding="utf-8")
                logger.info("Wrote ProjectVersion.txt with m_EditorVersion=%s", target_version)
            else:
                try:
                    txt = pv.read_text(encoding="utf-8", errors="replace")
                    if "m_EditorVersion:" not in txt:
                        pv.write_text(f"m_EditorVersion: {target_version}\n", encoding="utf-8")
                        logger.info("Updated ProjectVersion.txt with m_EditorVersion=%s", target_version)
                except Exception:
                    pv.write_text(f"m_EditorVersion: {target_version}\n", encoding="utf-8")
                    logger.info("Rewrote ProjectVersion.txt with m_EditorVersion=%s (read failed)", target_version)
        except Exception as e:
            logger.warning("Failed to ensure ProjectVersion.txt: %s", e)
        
        # Create .agp directory for project metadata
        agp_dir = project_dir / ".agp"
        agp_dir.mkdir(exist_ok=True)
        
        # Create context and logs directories at project root
        (project_dir / "context").mkdir(exist_ok=True)
        (project_dir / "logs").mkdir(exist_ok=True)
        
        # Merge user settings with defaults
        default_settings = {
            "version_schema": "1.0",
            "default_context_path": "context",
            "default_logs_path": "logs"
        }
        if settings:
            default_settings.update(settings)
        
        # Create project.json file
        project_data = {
            "id": project_id,
            "name": project_name,
            "version": "1.0.0",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "updated_at": datetime.utcnow().isoformat() + "Z",
            "type": "ai-gamedev-project",
            "settings": default_settings,
            "agent": {
                "adapter": "cli_generic",
                "executable": "python",
                "args": ["-u", "-m", "bridges.mcp_adapter"],
                "env": {},
                "default_timeout": 5.0,
                "terminate_grace": 3.0
            }
        }
        
        project_json_path = agp_dir / "project.json"
        with open(project_json_path, "w", encoding="utf-8") as f:
            json.dump(project_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Project structure created successfully at {project_dir}")
        
        return project_dir
    
    def _project_db_to_model(self, project_db: ProjectDB) -> Project:
        """Convert database model to API model.
        
        Args:
            project_db: Database project model
            
        Returns:
            API project model
        """
        project_path = self.projects_root / project_db.path

        # Read manifest if it exists
        manifest_path = project_path / ".agp" / "project.json"
        manifest: dict | None = None
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
            except Exception as e:
                logger.warning("Failed to read manifest for project %s at %s: %s", project_db.id, manifest_path, e)
                manifest = None

        from datetime import datetime

        def _parse_dt(val: str | None) -> datetime:
            if not val:
                return datetime.utcnow()
            try:
                # Handle trailing Z
                if isinstance(val, str) and val.endswith("Z"):
                    return datetime.fromisoformat(val.replace("Z", "+00:00"))
                return datetime.fromisoformat(val)  # type: ignore[arg-type]
            except Exception:
                return datetime.utcnow()

        created_at = _parse_dt((manifest or {}).get("created_at"))
        updated_at = _parse_dt((manifest or {}).get("updated_at"))
        settings_obj = (manifest or {}).get("settings", {})
        settings = settings_obj if isinstance(settings_obj, dict) else {}
        description = (manifest or {}).get("description")

        return Project(
            id=project_db.id,
            name=project_db.name,
            description=description,
            status="active" if project_db.active else "inactive",
            createdAt=created_at,
            updatedAt=updated_at,
            settings=settings,
        )
    
    def list_projects(self) -> List[Project]:
        """List all projects.
        
        Returns:
            List of all projects
        """
        try:
            projects_db = self.db.list_projects()
            logger.debug("DB returned %d projects", len(projects_db))
            out: List[Project] = []
            for p in projects_db:
                try:
                    out.append(self._project_db_to_model(p))
                except Exception as e:
                    logger.exception("Failed to map project '%s': %s", getattr(p, 'id', '?'), e)
            logger.debug("Mapped %d projects for API response", len(out))
            return out
        except Exception as e:
            logger.exception("Error listing projects: %s", e)
            raise
    
    def get_project(self, project_id: str) -> Optional[Project]:
        """Get a project by ID.
        
        Args:
            project_id: Project ID
            
        Returns:
            Project if found, None otherwise
        """
        project_db = self.db.get_project(project_id)
        if project_db:
            return self._project_db_to_model(project_db)
        return None
    
    def create_project(self, create_data: CreateProject) -> Project:
        """Create a new project.
        
        Args:
            create_data: Project creation data
            
        Returns:
            Created project
            
        Raises:
            ValueError: If project name is invalid
        """
        # Generate unique project ID
        project_id = self._generate_project_id(create_data.name)
        
        # Create filesystem structure
        project_path = self._create_project_structure(project_id, create_data.name, create_data.settings)
        
        # Create database entry
        project_db = ProjectDB(
            id=project_id,
            name=create_data.name,
            path=project_id,  # Relative path from projects root
            active=False
        )
        
        created_project = self.db.create_project(project_db)
        
        return self._project_db_to_model(created_project)
    
    def select_active_project(self, project_id: str) -> bool:
        """Set a project as active.
        
        Args:
            project_id: ID of project to activate
            
        Returns:
            True if project was activated successfully, False if not found
        """
        return self.db.set_active_project(project_id)
    
    def get_active_project(self) -> Optional[Project]:
        """Get the currently active project.
        
        Returns:
            Active project if any, None otherwise
        """
        active_project = self.db.get_active_project()
        if active_project:
            return self._project_db_to_model(active_project)
        return None
    
    def delete_project(self, project_id: str, purge_fs: bool = False) -> bool:
        """Delete a project.
        
        By default deletes only the database record (preserves filesystem).
        If ``purge_fs`` is True, also removes the project's folder under ``projects_root``.
        
        Args:
            project_id: Project ID to delete
            purge_fs: Whether to remove the project directory from disk
            
        Returns:
            True if project was deleted, False if not found
        """
        # Delete DB record first
        ok = self.db.delete_project(project_id)
        if not ok:
            return False
        
        # Optionally remove filesystem
        if purge_fs:
            try:
                project_dir = self.projects_root / project_id
                if project_dir.exists() and project_dir.is_dir():
                    shutil.rmtree(project_dir, ignore_errors=True)
            except Exception:
                # We already removed DB record; ignore FS purge errors to avoid 404 mismatches
                pass
        return True


# Global project service instance
project_service = ProjectService()
