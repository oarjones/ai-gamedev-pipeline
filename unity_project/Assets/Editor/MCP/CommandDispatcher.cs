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
                            case "get_gameobject_details":
                                try
                                {
                                    if (queryMessage.data.params_ != null && queryMessage.data.params_.ContainsKey("instanceId"))
                                    {
                                        int instanceId = int.Parse(queryMessage.data.params_["instanceId"]);
                                        string gameObjectDetailsJson = EnvironmentScanner.GetGameObjectDetailsAsJson(instanceId);
                                        queryResponse = new UnityResponse
                                        {
                                            request_id = queryMessage.data.request_id,
                                            status = "success",
                                            payload = gameObjectDetailsJson
                                        };
                                    }
                                    else
                                    {
                                        queryResponse = new UnityResponse
                                        {
                                            request_id = queryMessage.data.request_id,
                                            status = "error",
                                            payload = JsonUtility.ToJson(new { error = "Missing 'instanceId' parameter for get_gameobject_details query." })
                                        };
                                    }
                                }
                                catch (Exception ex)
                                {
                                    Debug.LogError($"[MCP] Error getting GameObject details: {ex.Message}\n{ex.StackTrace}");
                                    queryResponse = new UnityResponse
                                    {
                                        request_id = queryMessage.data.request_id,
                                        status = "error",
                                        payload = JsonUtility.ToJson(new { error = $"Error getting GameObject details: {ex.Message}" })
                                    };
                                }
                                break;
                            case "get_project_files":
                                try
                                {
                                    if (queryMessage.data.params_ != null && queryMessage.data.params_.ContainsKey("path"))
                                    {
                                        string path = queryMessage.data.params_["path"];
                                        string projectFilesJson = EnvironmentScanner.GetProjectFilesAsJson(path);
                                        queryResponse = new UnityResponse
                                        {
                                            request_id = queryMessage.data.request_id,
                                            status = "success",
                                            payload = projectFilesJson
                                        };
                                    }
                                    else
                                    {
                                        queryResponse = new UnityResponse
                                        {
                                            request_id = queryMessage.data.request_id,
                                            status = "error",
                                            payload = JsonUtility.ToJson(new { error = "Missing 'path' parameter for get_project_files query." })
                                        };
                                    }
                                }
                                catch (Exception ex)
                                {
                                    Debug.LogError($"[MCP] Error getting project files: {ex.Message}\n{ex.StackTrace}");
                                    queryResponse = new UnityResponse
                                    {
                                        request_id = queryMessage.data.request_id,
                                        status = "error",
                                        payload = JsonUtility.ToJson(new { error = $"Error getting project files: {ex.Message}" })
                                    };
                                }
                                break;
                            default:
                                Debug.LogWarning($"[MCP] Unknown query action: {queryMessage.data.action}");
                                queryResponse = new UnityResponse
                                {
                                    request_id = queryMessage.data.request_id,
                                    status = "error",
                                    payload = JsonUtility.ToJson(new { error = $"Unknown query action: {queryMessage.data.action}" })
                                };
                                break;
                        }