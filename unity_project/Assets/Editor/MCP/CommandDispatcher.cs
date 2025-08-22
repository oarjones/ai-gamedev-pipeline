// En: Assets/Editor/MCP/CommandDispatcher.cs

using System;
using System.Collections.Concurrent;
using UnityEditor;

[InitializeOnLoad]
public static class CommandDispatcher
{
    // Una única cola que almacena acciones (bloques de código) a ejecutar.
    private static readonly ConcurrentQueue<Action> actionQueue = new ConcurrentQueue<Action>();

    static CommandDispatcher()
    {
        EditorApplication.update += OnEditorUpdate;
    }

    /// <summary>
    /// Añade una acción a la cola para ser ejecutada en el hilo principal de Unity.
    /// </summary>
    /// <param name="action">La acción a ejecutar.</param>
    public static void EnqueueAction(Action action)
    {
        if (action != null)
        {
            actionQueue.Enqueue(action);
        }
    }

    /// <summary>
    /// En cada tick del editor, procesa una acción de la cola.
    /// </summary>
    private static void OnEditorUpdate()
    {
        if (actionQueue.TryDequeue(out Action action))
        {
            action.Invoke();
        }
    }
}