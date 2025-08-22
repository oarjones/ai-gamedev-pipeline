using UnityEngine;
using UnityEditor;
using WebSocketSharp;
using System;
using System.Collections.Generic;

[InitializeOnLoad]
public static class MCPWebSocketClient
{
    private static WebSocket ws;

    static MCPWebSocketClient()
    {
        EditorApplication.delayCall += Initialize;
    }

    private static void Initialize()
    {
        string url = "ws://127.0.0.1:8001/ws/unity";
        ws = new WebSocket(url);

        ws.OnOpen += (sender, e) => Debug.Log("[MCP] Conectado al servidor.");
        ws.OnMessage += OnMessageReceived;
        ws.OnError += (sender, e) => Debug.LogError("[MCP] Error: " + e.Message);
        ws.OnClose += (sender, e) => Debug.Log("[MCP] Desconectado del servidor.");

        ws.Connect();

        Application.logMessageReceived += HandleLog;
        EditorApplication.quitting += Disconnect;
    }

    private static void OnMessageReceived(object sender, MessageEventArgs e)
    {
        Debug.Log("[MCP] Mensaje recibido: " + e.Data);
        try
        {
            // First, try to parse as a generic message to determine type
            var baseMessage = JsonUtility.FromJson<BaseMessage>(e.Data);

            if (baseMessage.type == "command")
            {
                var commandMessage = JsonUtility.FromJson<CommandMessage>(e.Data);
                CommandDispatcher.ExecuteCommand(commandMessage.data, ws);
            }
            else if (baseMessage.type == "query")
            {
                var queryMessage = JsonUtility.FromJson<QueryMessage>(e.Data);
                // For now, just send a placeholder response
                UnityResponse response = new UnityResponse
                {
                    request_id = queryMessage.data.request_id,
                    status = "success",
                    payload = JsonUtility.ToJson(new { message = "Query received and processed (placeholder)." })
                };
                ws.Send(JsonUtility.ToJson(response));
            }
            else
            {
                Debug.LogWarning($"[MCP] Tipo de mensaje desconocido: {baseMessage.type}");
            }
        }
        catch (Exception ex)
        {
            Debug.LogError($"[MCP] Error al procesar mensaje: {ex.Message}\n{ex.StackTrace}");
        }
    }

    private static void HandleLog(string logString, string stackTrace, LogType type)
    {
        if (type == LogType.Error || type == LogType.Exception)
        {
            var logData = new
            {
                level = type.ToString(),
                message = logString,
                stackTrace = stackTrace
            };
            string jsonLog = JsonUtility.ToJson(logData);
            if (ws != null && ws.IsAlive)
            {
                ws.Send(jsonLog);
            }
        }
    }

    private static void Disconnect()
    {
        if (ws != null && ws.IsAlive)
        {
            ws.Close();
        }
    }
}

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