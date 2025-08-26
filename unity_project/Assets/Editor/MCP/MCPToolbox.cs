// En: unity_project/Assets/Editor/MCP/MCPToolbox.cs

using UnityEngine;
using UnityEditor;
using System;
using System.Reflection;
using System.Linq;
using Newtonsoft.Json.Linq;

/// <summary>
/// Contiene una colecci�n de m�todos est�ticos de alto nivel para manipular
/// el editor de Unity de forma segura y controlada desde el MCP.
/// Cada m�todo est� dise�ado para ser una operaci�n at�mica y segura.
/// </summary>
public static class MCPToolbox
{
    /// <summary>
    /// Crea un nuevo GameObject vac�o en la ra�z de la escena.
    /// </summary>
    /// <param name="name">El nombre para el nuevo GameObject.</param>
    /// <returns>El InstanceID del objeto reci�n creado.</returns>
    public static int CreateGameObject(string name)
    {
        var go = new GameObject(name);
        // Registra la creaci�n para que se pueda deshacer (Ctrl+Z)
        Undo.RegisterCreatedObjectUndo(go, $"Create {name}");
        Debug.Log($"[MCPToolbox] GameObject '{name}' creado con ID: {go.GetInstanceID()}");
        return go.GetInstanceID();
    }

    /// <summary>
    /// Busca un GameObject en la escena activa por su nombre.
    /// </summary>
    /// <param name="name">El nombre del GameObject a buscar.</param>
    /// <returns>El InstanceID del objeto si se encuentra; de lo contrario, -1.</returns>
    public static int FindGameObject(string name)
    {
        GameObject go = GameObject.Find(name);
        if (go != null)
        {
            return go.GetInstanceID();
        }
        Debug.LogWarning($"[MCPToolbox] No se pudo encontrar el GameObject con nombre '{name}'.");
        return -1;
    }

    /// <summary>
    /// A�ade un componente a un GameObject especificado por su InstanceID.
    /// </summary>
    /// <param name="instanceId">El InstanceID del GameObject de destino.</param>
    /// <param name="componentType">El nombre completo del tipo del componente (ej: "UnityEngine.Rigidbody").</param>
    /// <returns>Verdadero si el componente se a�adi� correctamente, falso en caso contrario.</returns>
    public static bool AddComponent(int instanceId, string componentType)
    {
        GameObject go = EditorUtility.InstanceIDToObject(instanceId) as GameObject;
        if (go == null)
        {
            Debug.LogError($"[MCPToolbox] AddComponent fall�: No se encontr� el GameObject con InstanceID {instanceId}.");
            return false;
        }

        // Busca el tipo en todos los ensamblados cargados para m�xima compatibilidad
        Type type = AppDomain.CurrentDomain.GetAssemblies()
            .SelectMany(assembly => assembly.GetTypes())
            .FirstOrDefault(t => t.FullName.Equals(componentType, StringComparison.OrdinalIgnoreCase));

        if (type == null)
        {
            Debug.LogError($"[MCPToolbox] AddComponent fall�: No se pudo encontrar el tipo de componente '{componentType}'.");
            return false;
        }

        if (typeof(MonoBehaviour).IsAssignableFrom(type))
        {
            // Para scripts, usamos AddComponent<T>()
            go.AddComponent(type);
        }
        else
        {
            // Para otros componentes de Unity, usamos Undo para registrar la acci�n
            Undo.AddComponent(go, type);
        }

        Debug.Log($"[MCPToolbox] Componente '{componentType}' a�adido a '{go.name}'.");
        return true;
    }

    /// <summary>
    /// Establece el valor de una propiedad en un componente de un GameObject.
    /// </summary>
    /// <param name="instanceId">El InstanceID del GameObject.</param>
    /// <param name="componentType">El nombre completo del tipo del componente.</param>
    /// <param name="propertyName">El nombre de la propiedad a modificar.</param>
    /// <param name="value">El nuevo valor para la propiedad (puede ser un tipo primitivo o un JObject para vectores, etc.).</param>
    /// <returns>Verdadero si la propiedad se estableci� correctamente, falso en caso contrario.</returns>
    public static bool SetComponentProperty(int instanceId, string componentType, string propertyName, object value)
    {
        GameObject go = EditorUtility.InstanceIDToObject(instanceId) as GameObject;
        if (go == null)
        {
            Debug.LogError($"[MCPToolbox] SetComponentProperty fall�: No se encontr� GameObject con ID {instanceId}.");
            return false;
        }

        Type type = AppDomain.CurrentDomain.GetAssemblies()
            .SelectMany(assembly => assembly.GetTypes())
            .FirstOrDefault(t => t.FullName.Equals(componentType, StringComparison.OrdinalIgnoreCase));

        if (type == null)
        {
            Debug.LogError($"[MCPToolbox] SetComponentProperty fall�: No se encontr� el tipo '{componentType}'.");
            return false;
        }

        Component comp = go.GetComponent(type);
        if (comp == null)
        {
            Debug.LogError($"[MCPToolbox] SetComponentProperty fall�: El GameObject '{go.name}' no tiene el componente '{componentType}'.");
            return false;
        }

        PropertyInfo propInfo = comp.GetType().GetProperty(propertyName, BindingFlags.Public | BindingFlags.Instance);
        if (propInfo == null || !propInfo.CanWrite)
        {
            Debug.LogError($"[MCPToolbox] SetComponentProperty fall�: La propiedad '{propertyName}' no existe o no se puede escribir en '{componentType}'.");
            return false;
        }

        try
        {
            object convertedValue = ConvertValue(value, propInfo.PropertyType);
            Undo.RecordObject(comp, $"Set {propertyName}");
            propInfo.SetValue(comp, convertedValue, null);
            EditorUtility.SetDirty(comp); // Marca el objeto como modificado para que los cambios se guarden
            Debug.Log($"[MCPToolbox] Propiedad '{propertyName}' de '{componentType}' en '{go.name}' establecida a '{convertedValue}'.");
            return true;
        }
        catch (Exception e)
        {
            Debug.LogError($"[MCPToolbox] SetComponentProperty fall� con excepci�n: {e.Message}");
            return false;
        }
    }

    /// <summary>
    /// Helper para convertir valores de JSON (JObject, primitivos) al tipo de destino de la propiedad.
    /// </summary>
    private static object ConvertValue(object value, Type targetType)
    {
        if (value is Newtonsoft.Json.Linq.JObject jObject)
        {
            // Maneja la conversi�n de tipos comunes de Unity desde un objeto JSON
            if (targetType == typeof(Vector3))
            {
                return new Vector3(jObject["x"].Value<float>(), jObject["y"].Value<float>(), jObject["z"].Value<float>());
            }
            if (targetType == typeof(Vector2))
            {
                return new Vector2(jObject["x"].Value<float>(), jObject["y"].Value<float>());
            }
            if (targetType == typeof(Quaternion))
            {
                return new Quaternion(jObject["x"].Value<float>(), jObject["y"].Value<float>(), jObject["z"].Value<float>(), jObject["w"].Value<float>());
            }
            if (targetType == typeof(Color))
            {
                return new Color(jObject["r"].Value<float>(), jObject["g"].Value<float>(), jObject["b"].Value<float>(), jObject["a"].Value<float>());
            }
        }

        // Para tipos Enum
        if (targetType.IsEnum && value is string stringValue)
        {
            return Enum.Parse(targetType, stringValue, true);
        }
        if (targetType.IsEnum && value is long longValue)
        {
            return Enum.ToObject(targetType, longValue);
        }

        // Para otros tipos, usa el conversor est�ndar
        return Convert.ChangeType(value, targetType);
    }
}