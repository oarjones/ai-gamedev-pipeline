using System.Collections.Concurrent;
using UnityEditor;
using UnityEngine;

[InitializeOnLoad]
public static class CommandDispatcher
{
    private static readonly ConcurrentQueue<CommandJob> jobQueue = new ConcurrentQueue<CommandJob>();

    static CommandDispatcher()
    {
        EditorApplication.update += OnEditorUpdate;
    }

    public static void EnqueueCommand(CommandJob job)
    {
        jobQueue.Enqueue(job);
    }

    private static void OnEditorUpdate()
    {
        if (jobQueue.TryDequeue(out CommandJob job))
        {
            // Ejecutar el código a través del CSharpRunner
            CommandResult result = CSharpRunner.Execute(job.CommandToExecute);

            // Serializar el resultado a JSON para devolverlo
            string jsonResult = JsonUtility.ToJson(result);

            // Completar la tarea para que el servidor HTTP pueda responder
            job.Tcs.SetResult(jsonResult);
        }
    }
}