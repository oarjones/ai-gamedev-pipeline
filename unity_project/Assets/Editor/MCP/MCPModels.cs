// En: Assets/Editor/MCP/MCPModels.cs

using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using Newtonsoft.Json.Serialization;

// --- ESTRUCTURAS PARA LA COMUNICACIÓN WEBSOCKET --- //

/// <summary>
/// Modelo principal para los mensajes que llegan desde el servidor MCP.
/// </summary>
public class UnityMessage
{
    public string type; // "command" o "query"
    public string request_id;
    public string action;
    public JToken payload; // Objeto JSON flexible para los parámetros específicos.
}

/// <summary>
/// Modelo principal para las respuestas que se envían de vuelta al servidor MCP.
/// </summary>
public class UnityResponse
{
    public string request_id;
    public string status; // "success" o "error"
    public object payload; // Objeto que será serializado a JSON con el resultado o el error.
}


// --- PAYLOADS ESPECÍFICOS --- //

public class CommandPayload
{
    public string code;
    public List<string> additional_references;
}

// REMOVED QueryParameters class

// --- RESULTADOS DE EJECUCIUCIÓN DE CÓDIGO --- //

public class CommandExecutionResult
{
    public bool success;
    public string output;
    public string error;
}

// --- HELPERS --- //

/// <summary>
/// Clase genérica para envolver listas y objetos. Originalmente para JsonUtility,
/// se mantiene por ahora para compatibilidad con EnvironmentScanner.
/// </summary>
public class Wrapper<T>
{
    public T data;
}

// --- MODELOS PARA DATOS DE UNITY --- //

public class GameObjectData
{
    public string name;
    public int instanceId;
    public List<GameObjectData> children = new List<GameObjectData>();
}

public class ComponentData
{
    public string type;
    public string json; // Propiedades del componente serializadas como JSON
}

public class GameObjectDetails
{
    public string name;
    public int instanceId;
    public List<ComponentData> components = new List<ComponentData>();
}

public class ProjectFilesDetails
{
    public string path;
    public List<string> directories;
    public List<string> files;
}

// --- RESOLVERS Y CONVERTERS DE NEWTONSOFT.JSON --- //

/// <summary>
/// ContractResolver personalizado para ignorar propiedades que causan problemas con Unity.
/// </summary>
public class UnityContractResolver : DefaultContractResolver
{
    protected override IList<JsonProperty> CreateProperties(Type type, MemberSerialization memberSerialization)
    {
        IList<JsonProperty> properties = base.CreateProperties(type, memberSerialization);

        // Ignorar propiedades problemáticas conocidas de Unity
        if (typeof(Component).IsAssignableFrom(type) || typeof(GameObject).IsAssignableFrom(type))
        {
            properties = properties.Where(p => p.PropertyName != "transform" && 
                                                 p.PropertyName != "gameObject" &&
                                                 p.PropertyName != "enabled" &&
                                                 p.PropertyName != "tag" &&
                                                 p.PropertyName != "hideFlags").ToList();
        }

        return properties;
    }
}