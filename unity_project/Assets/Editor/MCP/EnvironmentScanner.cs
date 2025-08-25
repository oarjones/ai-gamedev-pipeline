// En: Assets/Editor/MCP/EnvironmentScanner.cs

using UnityEngine;
using UnityEditor;
using UnityEngine.SceneManagement;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Linq;
using System;
using Newtonsoft.Json;

/// <summary>
/// Proporciona métodos para escanear y obtener información sobre el estado del editor de Unity.
/// </summary>
public static class EnvironmentScanner
{
    // --- Scene Hierarchy Serialization --- //

    public static object GetSceneHierarchy()
    {
        List<GameObjectData> rootObjectsData = new List<GameObjectData>();
        Scene activeScene = SceneManager.GetActiveScene();
        foreach (GameObject rootGameObject in activeScene.GetRootGameObjects())
        {
            rootObjectsData.Add(BuildGameObjectData(rootGameObject));
        }
        return new Wrapper<List<GameObjectData>> { data = rootObjectsData };
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

    public static object GetGameObjectDetails(int instanceId)
    {
        GameObject go = EditorUtility.InstanceIDToObject(instanceId) as GameObject;

        if (go == null)
        {
            return new { error = $"GameObject with InstanceID {instanceId} not found."
};
        }

        var details = new GameObjectDetails
        {
            name = go.name,
            instanceId = go.GetInstanceID(),
            components = new List<ComponentData>()
        };

        foreach (Component comp in go.GetComponents<Component>())
        {
            if (comp == null) continue;

            var componentData = new ComponentData
            {
                type = comp.GetType().FullName,
                json = JsonConvert.SerializeObject(comp, Formatting.None, new JsonSerializerSettings
                {
                    ReferenceLoopHandling = ReferenceLoopHandling.Ignore,
                    ContractResolver = new UnityContractResolver()
                })
            };
            details.components.Add(componentData);
        }

        return new Wrapper<GameObjectDetails> { data = details };
    }

    // --- Project Files Scanning --- //

    public static object GetProjectFiles(string relativePath)
    {
        try
        {
            string assetsPath = Application.dataPath;
            string normalizedRelativePath = (relativePath ?? "").Trim().Replace("\\", "/");
            string fullPath = Path.GetFullPath(Path.Combine(assetsPath, normalizedRelativePath));

            if (!fullPath.StartsWith(Path.GetFullPath(assetsPath)))
            {
                throw new Exception("Acceso denegado. La ruta está fuera del directorio del proyecto.");
            }

            if (!Directory.Exists(fullPath))
            {
                throw new DirectoryNotFoundException($"El directorio no existe: {fullPath}");
            }

            var details = new ProjectFilesDetails
            {
                path = normalizedRelativePath,
                directories = Directory.GetDirectories(fullPath).Select(Path.GetFileName).ToList(),
                files = Directory.GetFiles(fullPath).Where(f => !f.EndsWith(".meta")).Select(Path.GetFileName).ToList()
            };

            return new Wrapper<ProjectFilesDetails> { data = details };
        }
        catch (Exception e)
        {
            Debug.LogError($"[EnvironmentScanner] Error escaneando archivos: {e.Message}");
            return new { error = e.Message };
        }
    }

    // --- Screenshot --- //

    public static CommandExecutionResult TakeScreenshot()
    {
        try
        {
            int width = 1280;
            int height = 720;
            SceneView sv = SceneView.lastActiveSceneView ?? SceneView.focusedWindow as SceneView;
            var go = new GameObject("~TempScreenshotCamera") { hideFlags = HideFlags.HideAndDontSave };
            var cam = go.AddComponent<Camera>();
            cam.enabled = false;
            cam.clearFlags = CameraClearFlags.Skybox;
            cam.backgroundColor = Color.black;
            cam.cullingMask = ~0;

            if (sv != null && sv.camera != null)
            {
                go.transform.SetPositionAndRotation(sv.camera.transform.position, sv.camera.transform.rotation);
                cam.fieldOfView = sv.camera.fieldOfView;
            }
            else if (Camera.main != null)
            {
                go.transform.SetPositionAndRotation(Camera.main.transform.position, Camera.main.transform.rotation);
                cam.fieldOfView = Camera.main.fieldOfView;
            }
            else
            {
                go.transform.position = new Vector3(0, 1.5f, -5f);
                go.transform.LookAt(Vector3.zero);
                cam.fieldOfView = 60f;
            }

            var rt = new RenderTexture(width, height, 24, RenderTextureFormat.ARGB32);
            var prevActive = RenderTexture.active;
            var prevTarget = cam.targetTexture;

            try
            {
                cam.targetTexture = rt;
                cam.Render();

                RenderTexture.active = rt;
                var tex = new Texture2D(width, height, TextureFormat.RGBA32, false);
                tex.ReadPixels(new Rect(0, 0, width, height), 0, 0);
                tex.Apply();

                byte[] png = tex.EncodeToPNG();
                UnityEngine.Object.DestroyImmediate(tex);

                string base64 = Convert.ToBase64String(png);

                return new CommandExecutionResult
                {
                    success = true,
                    output = base64
                };
            }
            finally
            {
                cam.targetTexture = prevTarget;
                RenderTexture.active = prevActive;
                rt.Release();
                UnityEngine.Object.DestroyImmediate(rt);
                UnityEngine.Object.DestroyImmediate(go);
            }
        }
        catch (Exception e)
        {
            return new CommandExecutionResult
            {
                success = false,
                error = $"[Screenshot Error] {e.GetType().Name}: {e.Message}\n{e.StackTrace}"
            };
        }
    }
}
