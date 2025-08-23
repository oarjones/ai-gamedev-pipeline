// En: Assets/Editor/MCP/CommandDispatcher.cs

using System;
using System.Collections.Concurrent;
using UnityEditor;
using UnityEngine;

[InitializeOnLoad]
public static class CommandDispatcher
{
    private static readonly ConcurrentQueue<Action> actionQueue = new ConcurrentQueue<Action>();

    static CommandDispatcher()
    {
        EditorApplication.update += OnEditorUpdate;
    }

    public static void EnqueueAction(Action action)
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

    /// <summary>
    /// Punto de entrada para procesar todos los mensajes del WebSocket.
    /// </summary>
    public static void ProcessIncomingMessage(string jsonData)
    {
        var response = new UnityResponse();
        try
        {
            var message = JsonUtility.FromJson<UnityMessage>(jsonData);
            response.request_id = message.request_id;

            switch (message.type)
            {
                case "command":
                    var commandPayload = JsonUtility.FromJson<CommandPayload>(message.payload);
                    var commandResult = CSharpRunner.Execute(commandPayload.code, commandPayload.additional_references);
                    response.payload = JsonUtility.ToJson(commandResult);
                    response.status = commandResult.success ? "success" : "error";
                    break;

                case "query":
                    string queryPayload = ProcessQuery(message.action, message.payload);
                    response.payload = queryPayload;
                    response.status = "success";
                    break;

                default:
                    throw new Exception($"Tipo de mensaje desconocido: {message.type}");
            }
        }
        catch (Exception e)
        {
            Debug.LogError($"[CommandDispatcher] Error procesando mensaje: {e}");
            response.status = "error";
            response.payload = JsonUtility.ToJson(new { error = e.Message });
        }

        MCPWebSocketClient.SendResponse(response);
    }

    /// <summary>
    /// Enruta las 'queries' a la función correspondiente de EnvironmentScanner.
    /// </summary>
    private static string ProcessQuery(string action, string payload)
    {
        switch (action)
        {
            case "get_scene_hierarchy":
                return EnvironmentScanner.GetSceneHierarchyAsJson();

            case "get_gameobject_details":
                var detailsParams = JsonUtility.FromJson<QueryParameters>(payload);
                return EnvironmentScanner.GetGameObjectDetailsAsJson(detailsParams.instanceId);

            case "get_project_files":
                var filesParams = JsonUtility.FromJson<QueryParameters>(payload);
                return EnvironmentScanner.GetProjectFilesAsJson(filesParams.path);

            default:
                Debug.LogWarning($"Query desconocida recibida: {action}");
                throw new Exception($"Acción de query desconocida: {action}");
        }
    }
}