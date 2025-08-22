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
        CommandDispatcher.DispatchMessage(e.Data, ws);
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

