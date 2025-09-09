from __future__ import annotations

import hashlib
import json
import os
import shutil
import tarfile
from pathlib import Path
from typing import List, Optional


class UnityPackageBuilder:
    """
    Minimal, offline-friendly builder that creates a distributable archive
    for the MCP Bridge. Note: real .unitypackage uses Unity's asset export format;
    we produce a .tar.gz with the intended folder structure for portability.
    """

    def __init__(self, temp_dir: Optional[str] = None):
        self.temp_dir = Path(temp_dir or ".mcp_build").resolve()
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def create_package(self, source_dir: str, output_path: str) -> Path:
        src = Path(source_dir).resolve()
        out = Path(output_path).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)

        # Copy source into a temp directory with normalized structure
        staging = self.temp_dir / "MCPBridge"
        if staging.exists():
            shutil.rmtree(staging)
        shutil.copytree(src, staging)

        # Ensure package.json exists
        pkg_json = staging / "package.json"
        if not pkg_json.exists():
            pkg_json.write_text(json.dumps({"name": "com.mcp.bridge", "version": "1.0.0"}, indent=2), encoding="utf-8")

        # Create tar.gz
        with tarfile.open(out, "w:gz") as tar:
            tar.add(staging, arcname="MCPBridge")
        return out

    def add_dependencies(self, package_path: str, deps: List[str]) -> None:
        # Append dependency list to a sidecar JSON metadata for the archive
        meta_path = Path(package_path).with_suffix(Path(package_path).suffix + ".deps.json")
        meta = {"dependencies": deps}
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    def sign_package(self, package_path: str, certificate: str) -> str:
        # Simple SHA256 hash + certificate tag; not cryptographically secure signing
        h = hashlib.sha256(Path(package_path).read_bytes()).hexdigest()
        sig = json.dumps({"hash": h, "cert": certificate}, indent=2)
        sig_path = Path(package_path).with_suffix(Path(package_path).suffix + ".sig.json")
        sig_path.write_text(sig, encoding="utf-8")
        return h

    def create_installer_script(self, target_dir: str) -> Path:
        target = Path(target_dir) / "Assets" / "Editor" / "MCPBridge" / "Installer" / "AutoInstaller.cs"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_AUTO_INSTALLER_CONTENTS, encoding="utf-8")
        return target

    def validate_package(self, package_path: str) -> List[str]:
        errors: List[str] = []
        p = Path(package_path)
        if not p.exists():
            errors.append("Package path does not exist")
        if p.suffixes[-2:] != [".tar", ".gz"] and p.suffix != ".unitypackage":
            errors.append("Unexpected package extension; expected .unitypackage or .tar.gz")
        # Validate sidecar files if present
        return errors


_AUTO_INSTALLER_CONTENTS = """
using UnityEditor;
using UnityEngine;
using System;
using System.IO;

[InitializeOnLoad]
public class MCPAutoInstaller
{
    private const string VERSION = "1.0.0";
    private static readonly string MARKER_FILE = ".mcp_installed";

    static MCPAutoInstaller()
    {
        EditorApplication.delayCall += CheckAndInstall;
    }

    private static string ProjectRoot() {
        var assets = Application.dataPath;
        return Directory.GetParent(assets).FullName;
    }

    private static bool IsInstalled() {
        return File.Exists(Path.Combine(ProjectRoot(), MARKER_FILE));
    }

    private static void CheckAndInstall()
    {
        if (!IsInstalled()) {
            ShowWelcomeWindow();
            try {
                InstallCore();
                ConfigureSettings();
                RunPostInstall();
                CreateMarkerFile();
                Debug.Log("MCP Bridge installed successfully.");
            } catch (Exception ex) {
                Debug.LogError($"MCP Bridge installation failed: {ex.Message}");
            }
        } else {
            CheckForUpdates();
        }
    }

    private static void ShowWelcomeWindow() {
        MCPWelcomeWindow.ShowWindow();
    }

    private static void InstallCore() {
        DependencyResolver.CheckDependencies();
        // TODO: Copy MCP core scripts/resources if needed
    }

    private static void ConfigureSettings() {
        // TODO: Apply default project settings for MCP
    }

    private static void RunPostInstall() {
        var report = MCPHealthCheck.RunDiagnostics();
        Debug.Log($"MCP Health: {report}");
    }

    private static void CreateMarkerFile() {
        File.WriteAllText(Path.Combine(ProjectRoot(), MARKER_FILE), VERSION);
        AssetDatabase.Refresh();
    }

    private static void CheckForUpdates() {
        // TODO: Compare versions and run ConfigurationMigrator if needed
    }
}
""";

