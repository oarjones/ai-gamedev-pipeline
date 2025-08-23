// En: Assets/Editor/MCP/MCPWebSocketClient.cs

using UnityEngine;
using UnityEditor;
using WebSocketSharp;
using System;

[InitializeOnLoad]
public static class MCPWebSocketClient
{
    private static WebSocket ws;
    private static bool isInitialized = false;

    // Propiedad pública para que otras clases puedan enviar mensajes
    public static WebSocket Ws => ws;

    static MCPWebSocketClient()
    {
        EditorApplication.delayCall += Initialize;
    }

    private static void Initialize()
    {
        if (isInitialized) return;
        isInitialized = true;

        Debug.Log("[MCP] Iniciando cliente WebSocket...");
        try
        {
            ws = new WebSocket("ws://127.0.0.1:8001/ws/unity");

            ws.OnOpen += (sender, e) => Debug.Log("[MCP] Conexión establecida.");
            ws.OnMessage += OnMessageReceived;
            ws.OnError += (sender, e) => Debug.LogError($"[MCP] Error de WebSocket: {e.Message}");
            ws.OnClose += (sender, e) => Debug.LogError($"[MCP] Desconectado del servidor. Razón: {e.Reason}");

            EditorApplication.quitting += Disconnect;
            ws.Connect();
        }
        catch (Exception ex)
        {
            Debug.LogError($"[MCP] Excepción durante la inicialización: {ex}");
        }
    }

    private static void OnMessageReceived(object sender, MessageEventArgs e)
    {
        Debug.Log($"[MCP] Mensaje JSON recibido: {e.Data}");
        // La única responsabilidad es encolar el mensaje para que el Dispatcher lo procese
        // en el hilo principal de Unity.
        CommandDispatcher.EnqueueAction(() => CommandDispatcher.ProcessIncomingMessage(e.Data));
    }

    public static void SendResponse(UnityResponse response)
    {
        if (ws == null || !ws.IsAlive)
        {
            Debug.LogWarning("[MCP] No se puede enviar respuesta, el WebSocket no está conectado.");
            return;
        }
        string jsonResponse = JsonUtility.ToJson(response);
        Debug.Log($"[MCP] Enviando respuesta JSON: {jsonResponse}");
        ws.Send(jsonResponse);
    }

    private static void Disconnect()
    {
        if (ws != null && ws.IsAlive)
        {
            Debug.Log("[MCP] Desconectando del servidor...");
            ws.Close();
        }
    }
}