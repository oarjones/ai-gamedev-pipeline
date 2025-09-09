using UnityEditor;
using UnityEngine;
using System.Collections.Generic;
using System.IO;
using System;

public static class StateRecorder
{
    private static string ProjectRoot() => Directory.GetParent(Application.dataPath).FullName;
    private static string StateDir() {
        var p = Path.Combine(ProjectRoot(), ".state");
        if (!Directory.Exists(p)) Directory.CreateDirectory(p);
        return p;
    }

    [MenuItem("MCP Bridge/State/Record Scene State")]
    public static void RecordSceneState()
    {
        var list = new List<object>();
        foreach (var tr in GameObject.FindObjectsOfType<Transform>())
        {
            list.Add(new {
                name = tr.gameObject.name,
                pos = tr.position,
                rot = tr.rotation.eulerAngles,
                scale = tr.localScale
            });
        }
        var json = JsonUtility.ToJson(new Wrapper{ items = list.ToArray() }, true);
        File.WriteAllText(Path.Combine(StateDir(), "unity_scene.json"), json);
        Debug.Log($"Scene state recorded: {list.Count} objects");
    }

    public static void RecordObjectChange(GameObject obj)
    {
        var data = JsonUtility.ToJson(new ObjInfo
        {
            name = obj.name,
            pos = obj.transform.position,
            rot = obj.transform.rotation.eulerAngles,
            scale = obj.transform.localScale
        }, true);
        File.WriteAllText(Path.Combine(StateDir(), $"obj_{obj.GetInstanceID()}.json"), data);
    }

    public static void RecordComponentChange(Component comp)
    {
        var data = JsonUtility.ToJson(comp, true);
        File.WriteAllText(Path.Combine(StateDir(), $"comp_{comp.GetInstanceID()}.json"), data);
    }

    public static void RestoreFromCheckpoint(string checkpointId)
    {
        // Placeholder: In real flow this would call back-end to materialize scene
        Debug.Log($"RestoreFromCheckpoint not implemented (id={checkpointId})");
    }

    public static string GetStateDiff(string checkpointA, string checkpointB)
    {
        // Placeholder: In real flow this would call back-end diff
        return $"Diff between {checkpointA} and {checkpointB}: (not implemented)";
    }

    [Serializable]
    private class Wrapper { public object[] items; }

    [Serializable]
    private class ObjInfo {
        public string name;
        public Vector3 pos;
        public Vector3 rot;
        public Vector3 scale;
    }
}

