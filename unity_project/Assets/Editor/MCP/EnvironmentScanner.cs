using UnityEngine;
using UnityEditor;
using UnityEngine.SceneManagement;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Linq;

public static class EnvironmentScanner
{
    // --- Scene Hierarchy Serialization --- //
    [System.Serializable]
    public class GameObjectData
    {
        public string name;
        public int instanceId;
        public List<GameObjectData> children;

        public GameObjectData(GameObject go)
        {
            name = go.name;
            instanceId = go.GetInstanceID();
            children = new List<GameObjectData>();
        }
    }

    public static string GetSceneHierarchyAsJson()
    {
        List<GameObjectData> rootObjectsData = new List<GameObjectData>();
        Scene activeScene = SceneManager.GetActiveScene();

        foreach (GameObject rootGameObject in activeScene.GetRootGameObjects())
        {
            rootObjectsData.Add(BuildGameObjectData(rootGameObject));
        }

        Wrapper<List<GameObjectData>> wrapper = new Wrapper<List<GameObjectData>> { data = rootObjectsData };
        return JsonUtility.ToJson(wrapper, true);
    }

    private static GameObjectData BuildGameObjectData(GameObject go)
    {
        GameObjectData data = new GameObjectData(go);

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
        GameObject go = EditorUtility.InstanceIDToObject(instanceId) as GameObject;

        if (go == null)
        {
            return JsonUtility.ToJson(new { error = $"GameObject with InstanceID {instanceId} not found."
        });
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

            // Use reflection to get public properties
            PropertyInfo[] properties = comp.GetType().GetProperties(BindingFlags.Public | BindingFlags.Instance);
            foreach (PropertyInfo prop in properties)
            {
                // Filter out properties that are not easily serializable or can cause issues
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

        Wrapper<GameObjectDetails> wrapper = new Wrapper<GameObjectDetails> { data = details };
        return JsonUtility.ToJson(wrapper, true);
    }

    // --- Project Files Scanning --- //
    [System.Serializable]
    public class ProjectFilesDetails
    {
        public List<string> directories;
        public List<string> files;
    }

    public static string GetProjectFilesAsJson(string relativePath)
    {
        string assetsPath = Application.dataPath;
        string fullPath = Path.Combine(assetsPath, relativePath).Replace("\", "/");

        // Security check: Ensure the path is within the Assets folder
        if (!fullPath.StartsWith(assetsPath) || Path.GetFullPath(fullPath).Contains(".."))
        {
            return JsonUtility.ToJson(new { error = $