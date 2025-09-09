using UnityEngine;
using System.Net.Sockets;
using System.IO;

public class HealthReport
{
    private System.Text.StringBuilder sb = new System.Text.StringBuilder();
    public void Add(string line) { sb.AppendLine(line); }
    public override string ToString() => sb.ToString();
}

public static class MCPHealthCheck
{
    public static HealthReport RunDiagnostics()
    {
        var report = new HealthReport();
        report.Add(CheckWebSocketServer());
        report.Add(CheckFilePermissions());
        report.Add(CheckPortAvailability());
        report.Add(CheckBlenderConnection());
        return report;
    }

    public static string CheckWebSocketServer()
    {
        // Placeholder: Ensure port pref set
        int port = UnityEditor.EditorPrefs.GetInt("MCP.Port", 17860);
        return $"WebSocket config present on port {port}";
    }

    public static string CheckFilePermissions()
    {
        try {
            var tmp = Path.Combine(Application.dataPath, "..", ".mcp_perm_test");
            File.WriteAllText(tmp, "ok");
            File.Delete(tmp);
            return "File permissions OK";
        } catch { return "File permissions ERROR"; }
    }

    public static string CheckPortAvailability()
    {
        int port = UnityEditor.EditorPrefs.GetInt("MCP.Port", 17860);
        try {
            var l = new TcpListener(System.Net.IPAddress.Loopback, port);
            l.Start(); l.Stop();
            return $"Port {port} available";
        } catch { return $"Port {port} in use"; }
    }

    public static string CheckBlenderConnection()
    {
        var path = UnityEditor.EditorPrefs.GetString("MCP.BlenderPath", "");
        return string.IsNullOrEmpty(path) ? "Blender path not set" : "Blender path set";
    }
}

