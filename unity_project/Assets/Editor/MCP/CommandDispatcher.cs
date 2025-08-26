// En: Assets/Editor/MCP/CommandDispatcher.cs

using System;
using System.Collections.Concurrent;
using UnityEditor;
using UnityEngine;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

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

    public static void ProcessIncomingMessage(string jsonData)
    {
        var response = new UnityResponse();
        try
        {
            var message = JsonConvert.DeserializeObject<UnityMessage>(jsonData);
            response.request_id = message.request_id;

            switch (message.type)
            {
                case "command":
                    var commandPayload = message.payload.ToObject<CommandPayload>();
                    var commandResult = CSharpRunner.Execute(commandPayload.code, commandPayload.additional_references);
                    response.payload = commandResult;
                    response.status = commandResult.success ? "success" : "error";
                    break;

                case "query":
                    response.payload = ProcessQuery(message.action, message.payload);
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
            response.payload = new { error = e.Message, details = e.ToString() };
        }

        MCPWebSocketClient.SendResponse(response);
    }

    private static object ProcessQuery(string action, JToken payload)
    {
        switch (action)
        {
            case "get_scene_hierarchy":
                return EnvironmentScanner.GetSceneHierarchy();

            case "capture_screenshot":
                return EnvironmentScanner.TakeScreenshot();

            case "get_gameobject_details":
                int instanceId;
                if (payload.Type == JTokenType.String) // If it's a JValue containing a string
                {
                    // Parse the string as JSON and then get the instanceId
                    JObject parsedPayload = JObject.Parse(payload.ToString());
                    instanceId = parsedPayload["instanceId"].Value<int>();
                }
                else // If it's a JObject directly
                {
                    instanceId = payload["instanceId"].Value<int>();
                }
                return EnvironmentScanner.GetGameObjectDetails(instanceId);

            case "get_project_files":
                string path;
                if (payload.Type == JTokenType.String) // If it's a JValue containing a string
                {
                    // Parse the string as JSON and then get the path
                    JObject parsedPayload = JObject.Parse(payload.ToString());
                    path = parsedPayload["path"].Value<string>();
                }
                else // If it's a JObject directly
                {
                    path = payload["path"].Value<string>();
                }
                return EnvironmentScanner.GetProjectFiles(path);

            default:
                Debug.LogWarning($"Query desconocida recibida: {action}");
                throw new Exception($"Acción de query desconocida: {action}");
        }
    }
}