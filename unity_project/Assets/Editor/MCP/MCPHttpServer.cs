using System.IO;
using System.Net;
using System.Threading;
using System.Threading.Tasks;
using UnityEditor;
using UnityEngine;

[InitializeOnLoad]
public static class MCPHttpServer
{
    private static readonly HttpListener listener = new HttpListener();
    private static readonly Thread listenerThread;

    static MCPHttpServer()
    {
        listener.Prefixes.Add("http://127.0.0.1:8002/execute/");
        listenerThread = new Thread(StartListener) { IsBackground = true };
        listenerThread.Start();
        EditorApplication.quitting += OnEditorQuitting;
        Debug.Log("[MCP] HTTP Server Started on port 8002.");
    }

    private static void StartListener()
    {
        listener.Start();
        while (listener.IsListening)
        {
            try
            {
                var context = listener.GetContext();
                Task.Run(() => HandleRequest(context));
            }
            catch (HttpListenerException)
            {
                // Listener was stopped.
                break;
            }
        }
    }

    private static async void HandleRequest(HttpListenerContext context)
    {
        var request = context.Request;
        var response = context.Response;

        if (request.HttpMethod != "POST")
        {
            response.StatusCode = (int)HttpStatusCode.MethodNotAllowed;
            response.Close();
            return;
        }

        try
        {
            string requestBody;
            using (var reader = new StreamReader(request.InputStream, request.ContentEncoding))
            {
                requestBody = await reader.ReadToEndAsync();
            }

            var commandData = JsonHelper.FromJson(requestBody);
            if (commandData == null || string.IsNullOrEmpty(commandData.command))
            {
                response.StatusCode = (int)HttpStatusCode.BadRequest;
                response.Close();
                return;
            }

            var job = new CommandJob
            {
                CommandToExecute = commandData.command,
                AdditionalReferences = commandData.additional_references,
                Tcs = new TaskCompletionSource<string>()
            };

            CommandDispatcher.EnqueueCommand(job);
            string result = await job.Tcs.Task;

            byte[] buffer = System.Text.Encoding.UTF8.GetBytes(result);
            response.ContentLength64 = buffer.Length;
            response.OutputStream.Write(buffer, 0, buffer.Length);
        }
        catch (System.Exception e)
        {
            Debug.LogError($"[MCP] Error handling request: {e.Message}");
            response.StatusCode = (int)HttpStatusCode.InternalServerError;
        }
        finally
        {
            response.Close();
        }
    }

    private static void OnEditorQuitting()
    {
        listener.Stop();
        listener.Close();
        listenerThread.Join();
        Debug.Log("[MCP] HTTP Server Stopped.");
    }
}