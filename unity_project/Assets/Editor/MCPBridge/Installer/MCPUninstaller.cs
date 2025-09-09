using UnityEditor;
using UnityEngine;
using System.IO;

public static class MCPUninstaller
{
    [MenuItem("MCP Bridge/Uninstall")]
    public static void Uninstall()
    {
        if (EditorUtility.DisplayDialog("Uninstall MCP Bridge?",
            "This will remove all MCP components", "Yes", "No"))
        {
            RemoveScripts();
            RemoveSettings();
            CleanupCache();
            AssetDatabase.Refresh();
            Debug.Log("MCP Bridge uninstalled (placeholder).");
        }
    }

    private static void RemoveScripts() { /* TODO */ }
    private static void RemoveSettings() { /* TODO */ }
    private static void CleanupCache() {
        var marker = Path.Combine(Directory.GetParent(Application.dataPath).FullName, ".mcp_installed");
        if (File.Exists(marker)) File.Delete(marker);
    }
}

