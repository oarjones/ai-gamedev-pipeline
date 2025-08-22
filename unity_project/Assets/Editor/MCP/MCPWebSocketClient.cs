using UnityEngine;
using UnityEditor;
using WebSocketSharp;
using System;

[InitializeOnLoad]
public static class MCPWebSocketClient
{
    private static WebSocket ws;
    private static bool isInitialized = false;

    static MCPWebSocketClient()
    {
        // Usamos delayCall para asegurarnos de que el editor está listo
        EditorApplication.delayCall += Initialize;
    }

    private static void Initialize()
    {
        // Añadimos un cerrojo para evitar inicializaciones múltiples
        if (isInitialized) return;
        isInitialized = true;


        Debug.Log("[MCP] Iniciando cliente WebSocket...");

        try
        {
            string url = "ws://127.0.0.1:8000/ws/unity";
            Debug.Log($"[MCP] Creando instancia de WebSocket con URL: {url}");

            ws = new WebSocket(url);

            // ---- ¡COMPROBACIÓN CRÍTICA! ----
            if (ws == null)
            {
                Debug.LogError("[MCP] ¡FALLO CRÍTICO! La instancia de WebSocket es NULA después de la creación. Comprueba la compatibilidad de la librería.");
                return; // Salimos para evitar más errores
            }

            Debug.Log("[MCP] Instancia de WebSocket creada. Suscribiendo eventos...");

            ws.OnOpen += (sender, e) => Debug.Log("[MCP] Conexión establecida con el servidor MCP.");
            ws.OnMessage += OnMessageReceived;
            ws.OnError += (sender, e) => Debug.LogError($"[MCP] Error de WebSocket: {e.Message}");
            ws.OnClose += (sender, e) => {
                Debug.LogError($"[MCP] Desconectado del servidor MCP. Código: {e.Code}, Razón: '{e.Reason}', Cierre limpio: {e.WasClean}");
            };

            Application.logMessageReceived += HandleLog;
            EditorApplication.quitting += Disconnect;

            Debug.Log("[MCP] Conectando al servidor...");
            ws.Connect();
        }
        catch (Exception ex)
        {
            Debug.LogError($"[MCP] Excepción durante la inicialización: {ex.ToString()}");
        }
    }

    private static void OnMessageReceived(object sender, MessageEventArgs e)
    {
        Debug.Log($"[MCP] Comando JSON recibido: {e.Data}");


        try
        {
            // Deserializamos la petición que llega desde el hilo de red
            var commandRequest = JsonUtility.FromJson<CommandRequest>(e.Data);

            // --- CAMBIO CLAVE ---
            // Creamos una 'Action' que encapsula el trabajo que SÓLO puede
            // hacerse en el hilo principal de Unity.
            Action mainThreadAction = () =>
            {
                try
                {
                    // 1. Ejecutamos el código a través del CSharpRunner (esto ahora es seguro)
                    var result = CSharpRunner.Execute(commandRequest.command, commandRequest.additional_references);

                    // 2. Serializamos el resultado
                    string jsonResult = JsonUtility.ToJson(result);

                    // 3. Enviamos la respuesta de vuelta (es seguro acceder a 'ws' desde aquí)
                    Debug.Log($"[MCP] Enviando resultado JSON: {jsonResult}");
                    ws.Send(jsonResult);
                }
                catch (Exception ex)
                {
                    Debug.LogError($"[MCP] Error ejecutando comando en el hilo principal: {ex}");
                    var errorResult = new CommandResult { success = false, error = ex.Message };
                    ws.Send(JsonUtility.ToJson(errorResult));
                }
            };

            // 4. Ponemos la acción en la cola del Dispatcher para que la ejecute de forma segura.
            CommandDispatcher.EnqueueAction(mainThreadAction);
        }
        catch (Exception ex)
        {
            Debug.LogError($"[MCP] Error al procesar el mensaje entrante: {ex}");
            var errorResult = new CommandResult { success = false, error = $"Error de deserialización o encolado: {ex.Message}" };
            ws.Send(JsonUtility.ToJson(errorResult));
        }
    }

    private static void HandleLog(string logString, string stackTrace, LogType type)
    {
        if (ws == null || !ws.IsAlive) return;

        if (type == LogType.Error || type == LogType.Exception)
        {
            var logMessage = new { type = "log", level = type.ToString(), message = logString, stack = stackTrace };
            ws.Send(JsonUtility.ToJson(logMessage));
        }
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

// Asegúrate de que esta clase también está en un fichero o al final de este
[Serializable]
public class CommandRequest
{
    public string command;
    public System.Collections.Generic.List<string> additional_references;
}