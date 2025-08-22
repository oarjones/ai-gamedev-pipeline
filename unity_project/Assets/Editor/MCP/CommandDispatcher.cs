
using System;
using System.Collections.Concurrent;
using UnityEditor;
using UnityEngine;
using WebSocketSharp;

[InitializeOnLoad]
public static class CommandDispatcher
{
    private static readonly ConcurrentQueue<Action> actionQueue = new ConcurrentQueue<Action>();

    static CommandDispatcher()
    {
        EditorApplication.update += OnEditorUpdate;
    }

    public static void ExecuteCommand(CommandRequest commandRequest, WebSocket ws)
    {
        EnqueueAction(() =>
        {
            CommandResult result = CSharpRunner.Execute(commandRequest.command, commandRequest.additional_references);
            string jsonResult = JsonUtility.ToJson(result);
            ws.Send(jsonResult);
        });
    }

    private static void EnqueueAction(Action action)
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
}
