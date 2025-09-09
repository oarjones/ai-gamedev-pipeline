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
/// <summary>
/// Proporciona métodos de consulta para inspeccionar el estado del Editor de Unity
/// (jerarquía de escena, detalles de GameObjects, estructura de proyecto y capturas).
/// </summary>
public static class EnvironmentScanner
{
    // --- Scene Hierarchy Serialization --- //

    /// <summary>
    /// Serializa la jerarquía de la escena activa a un modelo ligero.
    /// </summary>
    /// <returns>Wrapper con una lista de GameObjectData raíz.</returns>
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

    /// <summary>
    /// Construye recursivamente un árbol de GameObjectData para un GameObject dado.
    /// </summary>
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

    /// <summary>
    /// Devuelve detalles serializados de un GameObject por InstanceID.
    /// </summary>
    /// <param name="instanceId">Identificador de instancia de Unity.</param>
    public static object GetGameObjectDetails(int instanceId)
    {
        GameObject go = EditorUtility.InstanceIDToObject(instanceId) as GameObject;

        if (go == null)
        {
            return new { error = $"GameObject with InstanceID {instanceId} not found." };
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

            // 1. Extraemos las propiedades seguras a un diccionario.
            Dictionary<string, object> safeProperties = GetSerializableProperties(comp);

            // 2. Serializamos ESE DICCIONARIO a una cadena JSON.
            // Esto mantiene el modelo ComponentData intacto.
            string jsonString = JsonConvert.SerializeObject(safeProperties, Formatting.None);

            var componentData = new ComponentData
            {
                type = comp.GetType().FullName,
                json = jsonString
            };
            details.components.Add(componentData);
        }

        return new Wrapper<GameObjectDetails> { data = details };
    }

    /// <summary>
    /// (NUEVO MÉTODO) Extrae de forma segura las propiedades serializables de un componente de Unity.
    /// </summary>
    /// <summary>
    /// Extrae de forma segura propiedades serializables de un componente de Unity,
    /// filtrando tipos complejos y propiedades problemáticas.
    /// </summary>
    private static Dictionary<string, object> GetSerializableProperties(Component comp)
    {
        var properties = new Dictionary<string, object>();
        if (comp == null) return properties;

        PropertyInfo[] componentProperties = comp.GetType().GetProperties(BindingFlags.Public | BindingFlags.Instance);

        foreach (var prop in componentProperties)
        {
            if (!prop.CanRead || prop.GetIndexParameters().Length > 0)
            {
                continue;
            }

            if (prop.IsDefined(typeof(ObsoleteAttribute), true))
            {
                continue;
            }

            try
            {
                object value = prop.GetValue(comp, null);

                switch (value)
                {
                    case Vector2 v:
                        properties[prop.Name] = new { v.x, v.y };
                        break;
                    case Vector3 v:
                        properties[prop.Name] = new { v.x, v.y, v.z };
                        break;
                    case Vector4 v:
                        properties[prop.Name] = new { v.x, v.y, v.z, v.w };
                        break;
                    case Quaternion q:
                        properties[prop.Name] = new { q.x, q.y, q.z, q.w };
                        break;
                    case Color c:
                        properties[prop.Name] = new { c.r, c.g, c.b, c.a };
                        break;
                    case string _:
                    case bool _:
                    case Enum _:
                        properties[prop.Name] = value;
                        break;
                    case sbyte _:
                    case byte _:
                    case short _:
                    case ushort _:
                    case int _:
                    case uint _:
                    case long _:
                    case ulong _:
                    case float _:
                    case double _:
                    case decimal _:
                        properties[prop.Name] = Convert.ToDouble(value);
                        break;
                    default:
                        // Ignoramos tipos complejos que no manejamos explícitamente.
                        break;
                }
            }
            catch (Exception)
            {
                // Ignoramos cualquier propiedad que lance un error al ser leída.
            }
        }

        return properties;
    }

    // --- Project Files Scanning --- //

    /// <summary>
    /// Lista directorios y archivos (sin .meta) bajo Assets/ respetando seguridad de ruta.
    /// </summary>
    /// <param name="relativePath">Ruta relativa bajo Assets/.</param>
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

    /// <summary>
    /// Captura una imagen de la vista de escena o cámara principal en PNG base64.
    /// </summary>
    public static object TakeScreenshot()
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

                //return new CommandExecutionResult
                //{
                //    success = true,
                //    output = base64
                //};

                return new Wrapper<ScreenshotData> { data = new ScreenshotData { image_base64 = base64 } };
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
