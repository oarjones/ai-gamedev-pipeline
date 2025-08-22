using Microsoft.CSharp;
using System;
using System.CodeDom.Compiler;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text;
using UnityEditor;
using UnityEngine;

public static class CSharpRunner
{
    public static CommandResult Execute(string code, List<string> additionalReferences)
    {
        if (code == "TAKE_SCREENSHOT")
        {
            return TakeScreenshot();
        }

        var result = new CommandResult();
        var stringBuilder = new StringBuilder();
        var logHandler = new LogHandler(stringBuilder);

        try
        {
            Application.logMessageReceived += logHandler.HandleLog;

            var assembly = CompileWithFallback(code, result, additionalReferences);
            if (assembly != null)
            {
                var type = assembly.GetType("DynamicExecutor");
                if (type == null)
                {
                    throw new InvalidOperationException("No se pudo encontrar el tipo 'DynamicExecutor' en el ensamblado compilado.");
                }

                var method = type.GetMethod("Run", BindingFlags.Public | BindingFlags.Static);
                if (method == null)
                {
                    throw new InvalidOperationException("No se pudo encontrar el método estático 'Run' en el tipo 'DynamicExecutor'.");
                }

                object returnValue = method.Invoke(null, null);

                result.Success = true;
                result.ReturnValue = SerializeReturnValue(returnValue);
            }
        }
        catch (Exception e)
        {
            result.Success = false;
            result.ErrorMessage = $"[Execution Error] {e.GetType().Name}: {e.Message}\n{e.StackTrace}";
        }
        finally
        {
            Application.logMessageReceived -= logHandler.HandleLog;
            result.ConsoleOutput = stringBuilder.ToString();
        }

        return result;
    }

    private static Assembly CompileWithFallback(string code, CommandResult result, List<string> additionalReferences)
    {
        var essentialAssemblies = GetEssentialAssemblies();
        if (additionalReferences != null)
        {
            // La unión de ensamblados no generará duplicados
            essentialAssemblies = essentialAssemblies.Union(additionalReferences.Select(GetAssemblyLocation).Where(p => p != null)).ToList();
        }

        Debug.Log($"[CSharpRunner] Intentando compilación rápida con {essentialAssemblies.Count} ensamblados.");
        LogAssemblies(essentialAssemblies);
        var (assembly, compilationErrors) = Compile(code, essentialAssemblies);

        if (assembly != null)
        {
            return assembly;
        }

        Debug.LogWarning($"[CSharpRunner] La compilación rápida falló. Reintentando con todos los ensamblados. Error original:\n{compilationErrors}");
        var allAssemblies = GetAllAssemblies();
        if (additionalReferences != null)
        {
            allAssemblies = allAssemblies.Union(additionalReferences.Select(GetAssemblyLocation).Where(p => p != null)).ToList();
        }

        Debug.Log($"[CSharpRunner] Intentando compilación completa con {allAssemblies.Count} ensamblados.");
        LogAssemblies(allAssemblies);
        var (fallbackAssembly, fallbackErrors) = Compile(code, allAssemblies);

        if (fallbackAssembly != null)
        {
            return fallbackAssembly;
        }

        result.Success = false;
        result.ErrorMessage = fallbackErrors;
        return null;
    }

    private static (Assembly, string) Compile(string code, IEnumerable<string> referencedAssemblies)
    {
        var provider = new CSharpCodeProvider();
        var parameters = new CompilerParameters();

        // El .Distinct() final asegura que no hay rutas de ensamblado duplicadas
        foreach (var assemblyPath in referencedAssemblies.Where(p => !string.IsNullOrEmpty(p)).Distinct())
        {
            parameters.ReferencedAssemblies.Add(assemblyPath);
        }

        parameters.GenerateInMemory = true;
        parameters.GenerateExecutable = false;

        string sourceCode = BuildSourceTemplate(code, out int lineOffset);
        CompilerResults results = provider.CompileAssemblyFromSource(parameters, sourceCode);

        if (results.Errors.HasErrors)
        {
            var errors = new StringBuilder();
            foreach (CompilerError error in results.Errors)
            {
                errors.AppendLine($"Line {error.Line - lineOffset}: {error.ErrorText}");
            }
            return (null, $"[Compilation Error]\n{errors.ToString()}");
        }

        return (results.CompiledAssembly, null);
    }

    private static string BuildSourceTemplate(string code, out int codeLineOffset)
    {
        var lines = code.Split(new[] { '\r', '\n' }, StringSplitOptions.None);
        var codeWithoutUsings = new StringBuilder();
        // HashSet gestiona automáticamente los 'usings' duplicados
        var agentUsings = new HashSet<string>();

        foreach (var line in lines)
        {
            string trimmedLine = line.Trim();
            if (trimmedLine.StartsWith("using ") && trimmedLine.EndsWith(";"))
            {
                agentUsings.Add(trimmedLine);
            }
            else
            {
                codeWithoutUsings.AppendLine(line);
            }
        }

        var defaultUsings = new HashSet<string>
        {
            "using UnityEngine;", "using UnityEditor;", "using System;", "using System.IO;",
            "using System.Linq;", "using System.Collections.Generic;", "using System.Reflection;"
        };

        // .Union() combina ambas listas sin duplicados
        var allUsings = defaultUsings.Union(agentUsings).ToList();

        var finalCode = new StringBuilder();
        allUsings.ForEach(u => finalCode.AppendLine(u));

        finalCode.AppendLine();
        finalCode.AppendLine("public static class DynamicExecutor {");
        finalCode.AppendLine("    public static object Run() {");
        finalCode.Append(codeWithoutUsings.ToString());
        finalCode.AppendLine("        return null;");
        finalCode.AppendLine("    }");
        finalCode.AppendLine("}");

        codeLineOffset = allUsings.Count + 4;

        return finalCode.ToString();
    }

    private static string SerializeReturnValue(object value)
    {
        if (value == null) return "null";
        if (value is UnityEngine.Object unityObject)
        {
            return JsonUtility.ToJson(new { name = unityObject.name, type = unityObject.GetType().FullName, instanceID = unityObject.GetInstanceID() });
        }
        return value.ToString();
    }

    #region Assembly Management

    private static List<string> GetEssentialAssemblies()
    {
        return new List<string>
        {
            typeof(System.Linq.Enumerable).Assembly.Location, typeof(System.Xml.XmlDocument).Assembly.Location,
            typeof(UnityEngine.GameObject).Assembly.Location, typeof(UnityEditor.Editor).Assembly.Location,
        }.Distinct().ToList();
    }

    private static List<string> GetAllAssemblies()
    {
        return AppDomain.CurrentDomain.GetAssemblies()
            .Where(a => !a.IsDynamic && !string.IsNullOrEmpty(a.Location) && !a.FullName.StartsWith("System") && !a.FullName.StartsWith("mscorlib"))
            .Select(a => a.Location)
            .Concat(GetEssentialAssemblies())
            .Distinct()
            .ToList();
    }

    private static string GetAssemblyLocation(string assemblyName)
    {
        // Añadimos una comprobación por si el agente envía la extensión .dll
        string cleanAssemblyName = assemblyName.EndsWith(".dll") ? Path.GetFileNameWithoutExtension(assemblyName) : assemblyName;
        return AppDomain.CurrentDomain.GetAssemblies()
            .FirstOrDefault(a => a.GetName().Name.Equals(cleanAssemblyName, StringComparison.OrdinalIgnoreCase))?.Location;
    }

    private static void LogAssemblies(List<string> assemblies)
    {
        var logBuilder = new StringBuilder("Usando los siguientes ensamblados para la compilación:\n");
        foreach (var asm in assemblies.Distinct())
        {
            logBuilder.AppendLine($"- {Path.GetFileName(asm)}");
        }
        Debug.Log(logBuilder.ToString());
    }

    #endregion

    //private static CommandResult TakeScreenshot()
    //{
    //    try
    //    {
    //        // 1. Obtener la ventana de la Escena (la vista principal del editor)
    //        var sceneView = SceneView.lastActiveSceneView;
    //        if (sceneView == null)
    //        {
    //            // Si no hay ninguna, intenta obtener la que está "focuseada"
    //            sceneView = SceneView.focusedWindow as SceneView;
    //        }
    //        if (sceneView == null)
    //        {
    //            throw new Exception("No se pudo encontrar una ventana de SceneView activa para realizar la captura.");
    //        }

    //        // 2. Obtener la cámara de esa vista de escena
    //        Camera sceneCamera = sceneView.camera;
    //        if (sceneCamera == null)
    //        {
    //            throw new Exception("La SceneView activa no tiene una cámara válida.");
    //        }

    //        // 3. Crear una RenderTexture temporal para dibujar la vista de la cámara
    //        // Usamos las dimensiones de la propia vista para una captura 1:1
    //        int width = (int)sceneView.position.width;
    //        int height = (int)sceneView.position.height;
    //        RenderTexture renderTexture = new RenderTexture(width, height, 24);

    //        // 4. Forzar a la cámara a renderizar en nuestra textura
    //        RenderTexture prevActive = RenderTexture.active;
    //        RenderTexture.active = renderTexture;
    //        sceneCamera.targetTexture = renderTexture;

    //        sceneCamera.Render();

    //        // 5. Leer los píxeles de la RenderTexture a una nueva Textura2D
    //        Texture2D resultTexture = new Texture2D(width, height, TextureFormat.RGB24, false);
    //        resultTexture.ReadPixels(new Rect(0, 0, width, height), 0, 0);
    //        resultTexture.Apply();

    //        // 6. Limpieza: restaurar el estado original para no afectar al editor
    //        sceneCamera.targetTexture = null;
    //        RenderTexture.active = prevActive;
    //        UnityEngine.Object.DestroyImmediate(renderTexture); // Liberar memoria

    //        // 7. Codificar la textura a PNG y luego a Base64
    //        byte[] bytes = resultTexture.EncodeToPNG();
    //        UnityEngine.Object.DestroyImmediate(resultTexture); // Liberar memoria

    //        string base64 = Convert.ToBase64String(bytes);

    //        return new CommandResult
    //        {
    //            Success = true,
    //            ReturnValue = base64,
    //            ConsoleOutput = "Screenshot of SceneView taken successfully."
    //        };
    //    }
    //    catch (Exception e)
    //    {
    //        return new CommandResult
    //        {
    //            Success = false,
    //            ErrorMessage = $"[Screenshot Error] {e.GetType().Name}: {e.Message}\n{e.StackTrace}"
    //        };
    //    }
    //}


    private static CommandResult TakeScreenshot()
    {
        try
        {
            // 1) Resolución deseada (puedes parametrizarla si quieres)
            int width = 1280;
            int height = 720;

            // 2) Sacamos referencia a la SceneView (si existe) para copiar su pose
            SceneView sv = SceneView.lastActiveSceneView ?? SceneView.focusedWindow as SceneView;

            // 3) Creamos cámara temporal (no persiste en escena/proyecto)
            var go = new GameObject("~TempScreenshotCamera") { hideFlags = HideFlags.HideAndDontSave };
            var cam = go.AddComponent<Camera>();
            cam.enabled = false; // la activamos solo para render explícito
            cam.clearFlags = CameraClearFlags.Skybox; // o Color si prefieres fondo sólido
            cam.backgroundColor = Color.black;
            cam.cullingMask = ~0; // todo

            // Copiar pose desde SceneView si hay; si no, desde Camera.main; si no, una pose por defecto
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

            // 4) (Opcional) Ajustes suaves para URP/HDRP vía reflexión (no rompe en proyectos Built-in)
            try
            {
                var urpType = Type.GetType("UnityEngine.Rendering.Universal.UniversalAdditionalCameraData, Unity.RenderPipelines.Universal.Runtime");
                if (urpType != null)
                {
                    var urp = go.GetComponent(urpType) ?? go.AddComponent(urpType);
                    urpType.GetProperty("renderPostProcessing")?.SetValue(urp, true);
                }
                var hdrpType = Type.GetType("UnityEngine.Rendering.HighDefinition.HDAdditionalCameraData, Unity.RenderPipelines.HighDefinition.Runtime");
                if (hdrpType != null)
                {
                    var hdrp = go.GetComponent(hdrpType) ?? go.AddComponent(hdrpType);
                    // No necesitamos tocar propiedades; con tener el componente ya asegura path correcto
                }
            }
            catch { /* best-effort, no-op */ }

            // 5) Render a RT y lectura
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

                return new CommandResult
                {
                    Success = true,
                    ReturnValue = base64,
                    ConsoleOutput = "Screenshot generated via temp camera (SceneView pose if available)."
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
            return new CommandResult
            {
                Success = false,
                ErrorMessage = $"[Screenshot Error] {e.GetType().Name}: {e.Message}\n{e.StackTrace}"
            };
        }
    }


    private class LogHandler
    {
        private readonly StringBuilder _stringBuilder;
        public LogHandler(StringBuilder stringBuilder) { _stringBuilder = stringBuilder; }
        public void HandleLog(string logString, string stackTrace, LogType type)
        {
            _stringBuilder.AppendLine($"[{type}] {logString}");
        }
    }
}