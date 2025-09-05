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

