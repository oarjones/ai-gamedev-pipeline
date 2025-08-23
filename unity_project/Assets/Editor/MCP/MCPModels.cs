// En: Assets/Editor/MCP/MCPModels.cs

using System;
using System.Collections.Generic;

// --- ESTRUCTURAS PARA LA COMUNICACIÓN WEBSOCKET --- //

/// <summary>
/// Modelo principal para los mensajes que llegan desde el servidor MCP.
/// </summary>
[Serializable]
public class UnityMessage
{
    public string type; // "command" o "query"
    public string request_id;
    public string action;
    public string payload; // JSON string que contiene los parámetros específicos
}

/// <summary>
/// Modelo principal para las respuestas que se envían de vuelta al servidor MCP.
/// </summary>
[Serializable]
public class UnityResponse
{
    public string request_id;
    public string status; // "success" o "error"
    public string payload; // JSON string con el resultado o el mensaje de error.
}


// --- PAYLOADS ESPECÍFICOS --- //

[Serializable]
public class CommandPayload
{
    public string code;
    public List<string> additional_references;
}

[Serializable]
public class QueryParameters
{
    public int instanceId;
    public string path;
}

// --- RESULTADOS DE EJECUCIÓN DE CÓDIGO --- //

[Serializable]
public class CommandExecutionResult
{
    public bool success;
    public string output;
    public string error;
}

// --- HELPERS --- //

/// <summary>
/// Clase genérica para envolver listas y objetos y que JsonUtility pueda serializarlos.
/// </summary>
[Serializable]
public class Wrapper<T>
{
    public T data;
}