using UnityEngine;
using UnityEditor;
using UnityEngine.SceneManagement;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Linq;
using System;

public static class EnvironmentScanner
{
    // --- Scene Hierarchy Serialization --- //
    [Serializable]
    public class GameObjectData
    {
        public string name;
        public int instanceId;
        public List<GameObjectData> children;
    }

    public static string GetSceneHierarchyAsJson()
    {
        List<GameObjectData> rootObjectsData = new List<GameObjectData>();
        Scene activeScene = SceneManager.GetActiveScene();
        foreach (GameObject rootGameObject in activeScene.GetRootGameObjects())
        {
            rootObjectsData.Add(BuildGameObjectData(rootGameObject));
        }
        return JsonUtility.ToJson(new Wrapper<List<GameObjectData>> { data = rootObjectsData }, true);
    }

    private static GameObjectData BuildGameObjectData(GameObject go)
    {
        var data = new GameObjectData { name = go.name, instanceId = go.GetInstanceID(), children = new List<GameObjectData>() };
        foreach (Transform childTransform in go.transform)
        {
            data.children.Add(BuildGameObjectData(childTransform.gameObject));
        }
        return data;
    }

    // --- GameObject Details Serialization --- //
    [System.Serializable]
    public class GameObjectDetails
    {
        public string name;
        public int instanceId;
        public bool isActive;
        public string tag;
        public int layer;
        public TransformDetails transform;
        public List<ComponentDetails> components;
    }

    [System.Serializable]
    public class TransformDetails
    {
        public Vector3 position;
        public Quaternion rotation;
        public Vector3 scale;
    }

    [System.Serializable]
    public class ComponentDetails
    {
        public string typeName;
        public List<PropertyDetail> properties;
    }

    [System.Serializable]
    public class PropertyDetail
    {
        public string name;
        public string value;
    }


    public static string GetGameObjectDetailsAsJson(int instanceId)
    {
        // El código existente aquí es correcto y no necesita cambios.
        // Lo omito por brevedad, pero debe permanecer como está.
        GameObject go = EditorUtility.InstanceIDToObject(instanceId) as GameObject;

        if (go == null)
        {
            return JsonUtility.ToJson(new { error = $"GameObject with InstanceID {instanceId} not found." });
        }

        GameObjectDetails details = new GameObjectDetails
        {
            name = go.name,
            instanceId = go.GetInstanceID(),
            isActive = go.activeInHierarchy,
            tag = go.tag,
            layer = go.layer,
            transform = new TransformDetails
            {
                position = go.transform.position,
                rotation = go.transform.rotation,
                scale = go.transform.localScale
            },
            components = new List<ComponentDetails>()
        };

        foreach (Component comp in go.GetComponents<Component>())
        {
            if (comp == null) continue;

            ComponentDetails compDetails = new ComponentDetails
            {
                typeName = comp.GetType().FullName,
                properties = new List<PropertyDetail>()
            };

            PropertyInfo[] properties = comp.GetType().GetProperties(BindingFlags.Public | BindingFlags.Instance);
            foreach (PropertyInfo prop in properties)
            {
                if (prop.CanRead && prop.GetIndexParameters().Length == 0 &&
                    (prop.PropertyType.IsPrimitive || prop.PropertyType == typeof(string) ||
                     prop.PropertyType == typeof(Vector2) || prop.PropertyType == typeof(Vector3) ||
                     prop.PropertyType == typeof(Vector4) || prop.PropertyType == typeof(Quaternion) ||
                     prop.PropertyType == typeof(Color) || prop.PropertyType == typeof(Bounds) ||
                     prop.PropertyType == typeof(Rect) || prop.PropertyType.IsEnum))
                {
                    try
                    {
                        object value = prop.GetValue(comp, null);
                        compDetails.properties.Add(new PropertyDetail { name = prop.Name, value = value != null ? value.ToString() : "null" });
                    }
                    catch (Exception e)
                    {
                        Debug.LogWarning($"[EnvironmentScanner] Could not get property {prop.Name} from {comp.GetType().Name}: {e.Message}");
                    }
                }
            }
            details.components.Add(compDetails);
        }

        return JsonUtility.ToJson(new Wrapper<GameObjectDetails> { data = details }, true);
    }


    // --- Project Files Scanning --- //
    [Serializable]
    public class ProjectFilesDetails
    {
        public List<string> directories = new List<string>();
        public List<string> files = new List<string>();
    }

    public static string GetProjectFilesAsJson(string relativePath)
    {
        try
        {
            string assetsPath = Application.dataPath;
            // Normalizar la ruta de entrada
            string normalizedRelativePath = (relativePath ?? "").Trim().Replace("\\", "/");
            string fullPath = Path.GetFullPath(Path.Combine(assetsPath, normalizedRelativePath));

            // Security check: Asegurarse de que la ruta sigue estando dentro de Assets
            if (!fullPath.StartsWith(Path.GetFullPath(assetsPath)))
            {
                throw new Exception("Acceso denegado. La ruta está fuera del directorio del proyecto.");
            }

            if (!Directory.Exists(fullPath))
            {
                throw new DirectoryNotFoundException($"El directorio no existe: {fullPath}");
            }

            var details = new ProjectFilesDetails();
            foreach (var dir in Directory.GetDirectories(fullPath))
            {
                details.directories.Add(Path.GetFileName(dir));
            }
            foreach (var file in Directory.GetFiles(fullPath))
            {
                // Ignorar los meta files
                if (!file.EndsWith(".meta"))
                {
                    details.files.Add(Path.GetFileName(file));
                }
            }

            return JsonUtility.ToJson(new Wrapper<ProjectFilesDetails> { data = details }, true);
        }
        catch (Exception e)
        {
            Debug.LogError($"[EnvironmentScanner] Error escaneando archivos: {e.Message}");
            return JsonUtility.ToJson(new { error = e.Message });
        }
    }

}