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
            Debug.Log($"[MCP] Executing command (placeholder): {job.CommandToExecute}");
            // In a future module, we will execute the command here.
            job.Tcs.SetResult($"Successfully executed (placeholder): {job.CommandToExecute}");
        }
    }
}