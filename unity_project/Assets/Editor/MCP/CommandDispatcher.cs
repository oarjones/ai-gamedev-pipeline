using System;
using System.Collections.Concurrent;
using UnityEditor;
using UnityEngine;
using WebSocketSharp;
using System.Collections.Generic;

[InitializeOnLoad]
public static class CommandDispatcher
{
    private static readonly ConcurrentQueue<Action> actionQueue = new ConcurrentQueue<Action>();

    static CommandDispatcher()
    {
        EditorApplication.update += OnEditorUpdate;
    }

    public static void DispatchMessage(string jsonData, WebSocket ws)
    {
        EnqueueAction(() =>
        {
            try
            {
                var baseMessage = JsonUtility.FromJson<BaseMessage>(jsonData);

                switch (baseMessage.type)
                {
                    case "command":
                        var commandMessage = JsonUtility.FromJson<CommandMessage>(jsonData);
                        CommandResult commandResult = CSharpRunner.Execute(commandMessage.data.command, commandMessage.data.additional_references);
                        ws.Send(JsonUtility.ToJson(commandResult));
                        break;
                    case "query":
                        var queryMessage = JsonUtility.FromJson<QueryMessage>(jsonData);
                        Debug.Log($"[MCP] Query received. Action: {queryMessage.data.action}");

                        UnityResponse queryResponse;
                        switch (queryMessage.data.action)
                        {
                            case "get_scene_hierarchy":
                                try
                                {
                                    string sceneHierarchyJson = EnvironmentScanner.GetSceneHierarchyAsJson();
                                    queryResponse = new UnityResponse
                                    {
                                        request_id = queryMessage.data.request_id,
                                        status = "success",
                                        payload = sceneHierarchyJson
                                    };
                                }
                                catch (Exception ex)
                                {
                                    Debug.LogError($"[MCP] Error getting scene hierarchy: {ex.Message}\n{ex.StackTrace}");
                                    queryResponse = new UnityResponse
                                    {
                                        request_id = queryMessage.data.request_id,
                                        status = "error",
                                        payload = JsonUtility.ToJson(new { error = $"Error getting scene hierarchy: {ex.Message}" })
                                    };
                                }
                                break;
                            default:
                                Debug.LogWarning($"[MCP] Unknown query action: {queryMessage.data.action}");
                                queryResponse = new UnityResponse
                                {
                                    request_id = queryMessage.data.request_id,
                                    status = "error",
                                    payload = JsonUtility.ToJson(new { error = $
                    default:
                        Debug.LogWarning($"[MCP] Unknown message type received: {baseMessage.type}");
                        break;
                }
            }
            catch (Exception ex)
            {
                Debug.LogError($"[MCP] Error dispatching message: {ex.Message}\n{ex.StackTrace}");
                // Attempt to send an error response if a request_id is present
                try
                {
                    var tempBaseMessage = JsonUtility.FromJson<BaseMessage>(jsonData);
                    if (tempBaseMessage.type == "query")
                    {
                        var tempQueryMessage = JsonUtility.FromJson<QueryMessage>(jsonData);
                        if (!string.IsNullOrEmpty(tempQueryMessage.data.request_id))
                        {
                            UnityResponse errorResponse = new UnityResponse
                            {
                                request_id = tempQueryMessage.data.request_id,
                                status = "error",
                                payload = JsonUtility.ToJson(new { error = $"Error processing query: {ex.Message}" })
                            };
                            ws.Send(JsonUtility.ToJson(errorResponse));
                        }
                    }
                }
                catch (Exception innerEx)
                {
                    Debug.LogError($"[MCP] Further error sending error response: {innerEx.Message}");
                }
            }
        });
    }

    private static void EnqueueAction(Action action)
    {
        if (action != null)
        {
            actionQueue.Enqueue(action);
        }
    }

    private static void OnEditorUpdate()
    {
        if (actionQueue.TryDequeue(out Action action))
        {
            action.Invoke();
        }
    }
}

// Re-defining these classes here as they are now directly used by CommandDispatcher
[Serializable]
public class BaseMessage
{
    public string type;
}

[Serializable]
public class CommandMessage
{
    public string type;
    public CommandRequest data;
}

[Serializable]
public class CommandRequest
{
    public string command;
    public List<string> additional_references;
}

[Serializable]
public class QueryMessage
{
    public string type;
    public QueryRequest data;
}

[Serializable]
public class QueryRequest
{
    public string action;
    public Dictionary<string, string> params_;
    public string request_id;
}

[Serializable]
public class UnityResponse
{
    public string request_id;
    public string status;
    public string payload;
}