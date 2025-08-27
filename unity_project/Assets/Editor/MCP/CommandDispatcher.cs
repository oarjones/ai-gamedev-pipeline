// En: Assets/Editor/MCP/CommandDispatcher.cs

using System;
using System.Collections.Concurrent;
using UnityEditor;
using UnityEngine;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using System.Reflection;

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
                    response.payload = ProcessCommand(message.action, message.payload);
                    if (response.payload is CommandExecutionResult cmdResult)
                    {
                        response.status = cmdResult.success ? "success" : "error";
                    }
                    else
                    {
                        response.status = "success";
                    }
                    break;

                case "query":
                    response.payload = ProcessQuery(message.action, message.payload);
                    response.status = "success"; 
                    break;

                // --- NUEVO CASE PARA LA TOOLBOX ---
                // Se añade la nueva lógica aquí, sin tocar lo demás.
                case "tool":
                    response.payload = ProcessToolAction(message.action, message.payload);
                    // El status dependerá del resultado de la herramienta
                    if (response.payload is CommandExecutionResult toolResult)
                    {
                        response.status = toolResult.success ? "success" : "error";
                    }
                    else
                    {
                        // Si la herramienta devuelve otro tipo de dato, asumimos éxito
                        response.status = "success";
                    }
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


    private static object ProcessCommand(string action, JToken payload)
    {
        try
        {
            switch (action)
            {
                case "ImportFBX":
                    string fbxPath = payload["path"].Value<string>();
                    GameObject prefab = AssetDatabase.LoadAssetAtPath<GameObject>(fbxPath);
                    if (prefab == null)
                        throw new Exception($"No se encontró prefab en la ruta {fbxPath}");
                    GameObject instance = PrefabUtility.InstantiatePrefab(prefab) as GameObject;
                    EnsureCameraAndLight();
                    return new { instanceId = instance.GetInstanceID() };

                case "EnsureCameraAndLight":
                    EnsureCameraAndLight();
                    return new { ensured = true };

                default:
                    var commandPayload = payload.ToObject<CommandPayload>();
                    return CSharpRunner.Execute(commandPayload.code, commandPayload.additional_references);
            }
        }
        catch (Exception e)
        {
            return new CommandExecutionResult
            {
                success = false,
                error = e.Message
            };
        }
    }

    private static void EnsureCameraAndLight()
    {
        if (Camera.main == null)
        {
            var camGO = new GameObject("Main Camera", typeof(Camera));
            camGO.tag = "MainCamera";
        }

        if (Object.FindObjectOfType<Light>() == null)
        {
            var lightGO = new GameObject("Directional Light", typeof(Light));
            lightGO.GetComponent<Light>().type = LightType.Directional;
        }
    }


    // --- NUEVO MÉTODO PARA PROCESAR ACCIONES DE LA TOOLBOX ---
    private static object ProcessToolAction(string action, JToken payload)
    {
        try
        {
            MethodInfo method = typeof(MCPToolbox).GetMethod(action, BindingFlags.Public | BindingFlags.Static);
            if (method == null)
            {
                throw new Exception($"La herramienta '{action}' no fue encontrada en MCPToolbox.");
            }

            // Convierte el payload de JToken a los parámetros que el método necesita
            var parameters = method.GetParameters();
            var args = new object[parameters.Length];
            var payloadObj = payload as JObject;

            for (int i = 0; i < parameters.Length; i++)
            {
                var param = parameters[i];
                if (payloadObj == null || !payloadObj.TryGetValue(param.Name, StringComparison.OrdinalIgnoreCase, out JToken token))
                {
                    throw new Exception($"Falta el argumento requerido '{param.Name}' para la herramienta '{action}'.");
                }
                args[i] = token.ToObject(param.ParameterType);
            }

            // Invoca el método de la Toolbox
            return method.Invoke(null, args);
        }
        catch (Exception e)
        {
            // Devolvemos un CommandExecutionResult en caso de error para mantener la consistencia
            return new CommandExecutionResult
            {
                success = false,
                error = $"Error ejecutando la herramienta '{action}': {e.Message}"
            };
        }
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