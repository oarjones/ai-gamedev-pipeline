using UnityEditor;
using UnityEngine;

public class StateTimelineWindow : EditorWindow
{
    private Vector2 scroll;
    private string[] mockHistory = new [] {
        "cp-001: Scene Saved",
        "cp-002: Player moved",
        "cp-003: Enemy added",
        "cp-004: Lighting tweaked",
    };

    [MenuItem("MCP Bridge/State/Timeline")] 
    public static void ShowWindow()
    {
        var w = GetWindow<StateTimelineWindow>(false, "MCP Timeline", true);
        w.minSize = new Vector2(520, 320);
        w.Show();
    }

    void OnGUI()
    {
        GUILayout.Label("State Timeline", EditorStyles.boldLabel);
        using (var sv = new EditorGUILayout.ScrollViewScope(scroll))
        {
            scroll = sv.scrollPosition;
            foreach (var item in mockHistory)
            {
                using (new GUILayout.HorizontalScope())
                {
                    GUILayout.Label(item);
                    if (GUILayout.Button("Rollback", GUILayout.Width(100)))
                    {
                        Debug.Log($"Rollback to {item}");
                    }
                }
            }
        }
        GUILayout.FlexibleSpace();
        using (new GUILayout.HorizontalScope())
        {
            if (GUILayout.Button("Record Scene State")) StateRecorder.RecordSceneState();
        }
    }
}

