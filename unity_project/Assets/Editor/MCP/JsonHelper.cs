using UnityEngine;

[System.Serializable]
public class CommandRequestData
{
    public string command;
    public List<string> additional_references;
}

public static class JsonHelper
{
    public static CommandRequestData FromJson(string json)
    {
        return JsonUtility.FromJson<CommandRequestData>(json);
    }
}