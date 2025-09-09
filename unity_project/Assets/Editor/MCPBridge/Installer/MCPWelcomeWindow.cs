using UnityEditor;
using UnityEngine;

public class MCPWelcomeWindow : EditorWindow
{
    private int port = 17860;
    private string blenderPath = "";
    private bool autoStart = true;

    public static void ShowWindow()
    {
        var w = GetWindow<MCPWelcomeWindow>(true, "MCP Bridge Setup", true);
        w.minSize = new Vector2(420, 260);
        w.Show();
    }

    void OnGUI()
    {
        GUILayout.Label("MCP Bridge", EditorStyles.boldLabel);
        EditorGUILayout.HelpBox("Configura MCP Bridge. Puedes cambiar estas opciones más tarde.", MessageType.Info);

        port = EditorGUILayout.IntField("WebSocket Port", port);
        blenderPath = EditorGUILayout.TextField("Blender Path", blenderPath);
        autoStart = EditorGUILayout.Toggle("Auto-start MCP Server", autoStart);

        GUILayout.FlexibleSpace();
        using (new GUILayout.HorizontalScope())
        {
            if (GUILayout.Button("Skip")) Close();
            if (GUILayout.Button("Install"))
            {
                // Persist minimal config (EditorPrefs for simplicity)
                EditorPrefs.SetInt("MCP.Port", port);
                EditorPrefs.SetString("MCP.BlenderPath", blenderPath);
                EditorPrefs.SetBool("MCP.AutoStart", autoStart);
                Close();
            }
        }
    }
}

