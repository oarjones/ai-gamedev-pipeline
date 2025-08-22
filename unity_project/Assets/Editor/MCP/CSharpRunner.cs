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
        try
        {
            // Usando CompileWithFallback como solicitaste
            var (assembly, compilationErrors) = CompileWithFallback(code, result, additionalReferences);

            if (assembly != null)
            {
                var type = assembly.GetType("DynamicExecutor");
                if (type == null) throw new InvalidOperationException("No se pudo encontrar el tipo 'DynamicExecutor'.");

                var method = type.GetMethod("Run", BindingFlags.Public | BindingFlags.Static);
                if (method == null) throw new InvalidOperationException("No se pudo encontrar el método estático 'Run'.");

                // La invocación ahora es segura porque este método se ejecuta en el hilo principal
                object returnValue = method.Invoke(null, null);

                result.success = true;
                // Aseguramos que el valor de retorno se asigna a 'output'
                result.output = SerializeReturnValue(returnValue);
            }
            else
            {
                result.success = false;
                result.error = compilationErrors;
            }
        }
        catch (Exception e)
        {
            result.success = false;
            result.error = $"[Execution Error] {e.GetType().Name}: {e.Message}\n{e.StackTrace}";
        }

        return result;
    }

    //public static CommandResult Execute(string code, List<string> additionalReferences)
    //{
    //    if (code == "TAKE_SCREENSHOT")
    //    {
    //        return TakeScreenshot();
    //    }

    //    var result = new CommandResult();
    //    var consoleOutputBuilder = new StringBuilder();
    //    var logHandler = new LogHandler(consoleOutputBuilder);

    //    try
    //    {
    //        Application.logMessageReceived += logHandler.HandleLog;

    //        var assembly = CompileWithFallback(code, result, additionalReferences);
    //        if (assembly != null)
    //        {
    //            var type = assembly.GetType("DynamicExecutor");
    //            if (type == null)
    //            {
    //                throw new InvalidOperationException("No se pudo encontrar el tipo 'DynamicExecutor' en el ensamblado compilado.");
    //            }

    //            var method = type.GetMethod("Run", BindingFlags.Public | BindingFlags.Static);
    //            if (method == null)
    //            {
    //                throw new InvalidOperationException("No se pudo encontrar el método estático 'Run' en el tipo 'DynamicExecutor'.");
    //            }

    //            object returnValue = method.Invoke(null, null);

    //            result.success = true;
    //            string serializedReturnValue = SerializeReturnValue(returnValue);
    //            string consoleOutput = consoleOutputBuilder.ToString();
    //            result.output = string.IsNullOrEmpty(consoleOutput) ? serializedReturnValue : $"{consoleOutput}\n---RETURN---\n{serializedReturnValue}";
    //        }
    //    }
    //    catch (Exception e)
    //    {
    //        result.success = false;
    //        result.error = $"[Execution Error] {e.GetType().Name}: {e.Message}\n{e.StackTrace}";
    //    }
    //    finally
    //    {
    //        Application.logMessageReceived -= logHandler.HandleLog;
    //        // Si ya hay un error, le añadimos el log de la consola para dar más contexto.
    //        if (!string.IsNullOrEmpty(result.error))
    //        {
    //            result.error += @"\n\n---CONSOLE OUTPUT---\" + consoleOutputBuilder.ToString();
    //        }
    //    }

    //    return result;
    //}

    private static (Assembly, string) CompileWithFallback(string code, CommandResult result, List<string> additionalReferences)
    {
        var essentialAssemblies = GetEssentialAssemblies();
        if (additionalReferences != null)
        {
            essentialAssemblies = essentialAssemblies.Union(additionalReferences.Select(GetAssemblyLocation).Where(p => p != null)).ToList();
        }

        var (assembly, compilationErrors) = Compile(code, essentialAssemblies);

        if (assembly != null)
        {
            return (assembly, compilationErrors);
        }

        Debug.LogWarning($"[CSharpRunner] La compilación rápida falló. Reintentando con todos los ensamblados. Error original:\n{compilationErrors}");
        var allAssemblies = GetAllAssemblies();
        if (additionalReferences != null)
        {
            allAssemblies = allAssemblies.Union(additionalReferences.Select(GetAssemblyLocation).Where(p => p != null)).ToList();
        }

        var (fallbackAssembly, fallbackErrors) = Compile(code, allAssemblies);

        if (fallbackAssembly != null)
        {
            return (fallbackAssembly, fallbackErrors);
        }

        result.success = false;
        result.error = fallbackErrors;
        return (null, fallbackErrors);
    }

    private static (Assembly, string) Compile(string code, IEnumerable<string> referencedAssemblies)
    {
        var provider = new CSharpCodeProvider();
        var parameters = new CompilerParameters();

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
        string cleanAssemblyName = assemblyName.EndsWith(".dll") ? Path.GetFileNameWithoutExtension(assemblyName) : assemblyName;
        return AppDomain.CurrentDomain.GetAssemblies()
            .FirstOrDefault(a => a.GetName().Name.Equals(cleanAssemblyName, StringComparison.OrdinalIgnoreCase))?.Location;
    }

    private static void LogAssemblies(List<string> assemblies)
    {
        // This method is for debugging and can be kept as is.
    }

    #endregion

    private static CommandResult TakeScreenshot()
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

                return new CommandResult
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
            return new CommandResult
            {
                success = false,
                error = $"[Screenshot Error] {e.GetType().Name}: {e.Message}\n{e.StackTrace}"
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