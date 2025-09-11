// En: Assets/Editor/MCP/MCPWebSocketClient.cs

using UnityEngine;
using UnityEditor;
using WebSocketSharp;
using System;
using Newtonsoft.Json;

/// <summary>
/// Cliente WebSocket del lado del Editor de Unity.
/// Mantiene una conexión con el MCP Bridge para recibir comandos y
/// enviar respuestas serializadas en JSON.
/// </summary>
[InitializeOnLoad]
public static class MCPWebSocketClient
{
    private static WebSocket ws;
    private static bool isInitialized = false;

    static MCPWebSocketClient()
    {
        EditorApplication.delayCall += Initialize;
    }

    /// <summary>
    /// Inicializa el cliente y establece la conexión WebSocket.
    /// Se invoca en el primer ciclo del Editor tras cargar scripts.
    /// </summary>
    private static void Initialize()
    {
        if (isInitialized) return;
        isInitialized = true;

        Debug.Log("[MCP] Iniciando cliente WebSocket...");
        try
        {
            ws = new WebSocket("ws://127.0.0.1:8001/ws/unity_editor");

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

    /// <summary>
    /// Callback de recepción de mensajes desde el Bridge.
    /// Encola el procesamiento en el hilo del Editor.
    /// </summary>
    private static void OnMessageReceived(object sender, MessageEventArgs e)
    {
        Debug.Log($"[MCP] Mensaje JSON recibido: {e.Data}");
        CommandDispatcher.EnqueueAction(() => CommandDispatcher.ProcessIncomingMessage(e.Data));
    }

    /// <summary>
    /// Envía una respuesta de Unity al Bridge por WebSocket.
    /// </summary>
    /// <param name="response">Objeto con request_id, status y payload.</param>
    public static void SendResponse(UnityResponse response)
    {
        if (ws == null || !ws.IsAlive)
        {
            Debug.LogWarning("[MCP] No se puede enviar respuesta, el WebSocket no está conectado.");
            return;
        }

        // Usamos Newtonsoft.Json para serializar la respuesta completa
        string jsonResponse = JsonConvert.SerializeObject(response, Formatting.Indented, new JsonSerializerSettings
        {
            ReferenceLoopHandling = ReferenceLoopHandling.Ignore
        });

        Debug.Log($"[MCP] Enviando respuesta JSON: {jsonResponse}");
        ws.Send(jsonResponse);
    }

    /// <summary>
    /// Cierra la conexión WebSocket de forma ordenada al salir del Editor.
    /// </summary>
    private static void Disconnect()
    {
        if (ws != null && ws.IsAlive)
        {
            Debug.Log("[MCP] Desconectando del servidor...");
            ws.Close();
        }
    }
}
