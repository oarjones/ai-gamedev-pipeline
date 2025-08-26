// En: unity_project/Assets/Editor/MCP/MCPToolbox.cs

using UnityEngine;
using UnityEditor;
using System;
using System.Reflection;

/// <summary>
/// Contiene una colección de métodos estáticos de alto nivel para manipular
/// el editor de Unity de forma segura y controlada desde el MCP.
/// </summary>
public static class MCPToolbox
{
    /// <summary>
    /// Crea un nuevo GameObject en la escena.
    /// </summary>
    /// <param name="name">El nombre del GameObject.</param>
    /// <returns>El InstanceID del objeto creado.</returns>
    public static int CreateGameObject(string name)
    {
        var go = new GameObject(name);
        Undo.RegisterCreatedObjectUndo(go, $"Create {name}");
        return go.GetInstanceID();
    }

    /// <summary>
    /// Busca un GameObject en la escena por su nombre.
    /// </summary>
    /// <param name="name">El nombre a buscar.</param>
    /// <returns>El InstanceID del objeto si se encuentra, de lo contrario -1.</returns>
    public static int FindGameObject(string name)
    {
        GameObject go = GameObject.Find(name);
        return go != null ? go.GetInstanceID() : -1;
    }

    /// <summary>
    /// Añade un componente a un GameObject.
    /// </summary>
    /// <param name="instanceId">El InstanceID del GameObject.</param>
    /// <param name="componentType">El nombre completo del tipo del componente (ej: "UnityEngine.Rigidbody").</param>
    /// <returns>Verdadero si el componente fue añadido, falso en caso contrario.</returns>
    public static bool AddComponent(int instanceId, string componentType)
    {
        GameObject go = EditorUtility.InstanceIDToObject(instanceId) as GameObject;
        if (go == null)
        {
            Debug.LogError($"[MCPToolbox] No se encontró el GameObject con InstanceID {instanceId}.");
            return false;
        }

        Type type = Type.GetType(componentType);
        if (type == null)
        {
            // Intenta buscar en los ensamblados de Unity si no es un tipo de sistema
            type = Assembly.Load("UnityEngine").GetType(componentType) ??
                   Assembly.Load("UnityEditor").GetType(componentType);
        }

        if (type == null)
        {
            Debug.LogError($"[MCPToolbox] No se pudo encontrar el tipo de componente '{componentType}'.");
            return false;
        }

        Undo.AddComponent(go, type);
        return true;
    }

    /// <summary>
    /// Establece el valor de una propiedad en un componente de un GameObject.
    /// </summary>
    /// <param name="instanceId">El InstanceID del GameObject.</param>
    /// <param name="componentType">El nombre completo del tipo del componente.</param>
    /// <param name="propertyName">El nombre de la propiedad a modificar.</param>
    /// <param name="value">El nuevo valor para la propiedad.</param>
    /// <returns>Verdadero si la propiedad se estableció correctamente, falso en caso contrario.</returns>
    public static bool SetComponentProperty(int instanceId, string componentType, string propertyName, object value)
    {
        GameObject go = EditorUtility.InstanceIDToObject(instanceId) as GameObject;
        if (go == null)
        {
            Debug.LogError($"[MCPToolbox] No se encontró el GameObject con InstanceID {instanceId}.");
            return false;
        }

        Type type = Type.GetType(componentType);
        if (type == null)
        {
            type = Assembly.Load("UnityEngine").GetType(componentType) ??
                   Assembly.Load("UnityEditor").GetType(componentType);
        }

        if (type == null)
        {
            Debug.LogError($"[MCPToolbox] No se pudo encontrar el tipo de componente '{componentType}'.");
            return false;
        }

        Component comp = go.GetComponent(type);
        if (comp == null)
        {
            Debug.LogError($"[MCPToolbox] El GameObject '{go.name}' no tiene el componente '{componentType}'.");
            return false;
        }

        PropertyInfo propInfo = type.GetProperty(propertyName);
        if (propInfo == null || !propInfo.CanWrite)
        {
            Debug.LogError($"[MCPToolbox] La propiedad '{propertyName}' no existe o no se puede escribir en el componente '{componentType}'.");
            return false;
        }

        try
        {
            // Convierte el valor al tipo correcto de la propiedad si es necesario
            object convertedValue = Convert.ChangeType(value, propInfo.PropertyType);
            Undo.RecordObject(comp, $"Set {propertyName}");
            propInfo.SetValue(comp, convertedValue, null);
            return true;
        }
        catch (Exception e)
        {
            Debug.LogError($"[MCPToolbox] Error al establecer la propiedad '{propertyName}': {e.Message}");
            return false;
        }
    }
}