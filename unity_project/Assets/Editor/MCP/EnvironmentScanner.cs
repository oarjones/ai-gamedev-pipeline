
using UnityEngine;
using UnityEditor;
using UnityEngine.SceneManagement;
using System.Collections.Generic;

public static class EnvironmentScanner
{
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

        // JsonUtility.ToJson does not serialize lists of custom classes directly as root elements.
        // We need to wrap it in a serializable class.
        Wrapper wrapper = new Wrapper { gameObjects = rootObjectsData };
        return JsonUtility.ToJson(wrapper, true); // 'true' for pretty print
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

    [System.Serializable]
    private class Wrapper
    {
        public List<GameObjectData> gameObjects;
    }
}
