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
    // Caché estática para no buscar los ensamblados en cada llamada
    private static Dictionary<string, string> _assemblyCache;

    public static CommandResult Execute(string code, List<string> additionalReferences)
    {
        if (code == "TAKE_SCREENSHOT")
        {
            return TakeScreenshot();
        }

        var result = new CommandResult();
        var logHandler = new LogHandler();

        try
        {
            Application.logMessageReceivedThreaded += logHandler.HandleLog;

            var (assembly, compilationErrors) = Compile(code, additionalReferences);
            if (assembly != null)
            {
                var type = assembly.GetType("DynamicExecutor");
                if (type == null) throw new InvalidOperationException("No se pudo encontrar el tipo 'DynamicExecutor'.");

                var method = type.GetMethod("Run", BindingFlags.Public | BindingFlags.Static);
                if (method == null) throw new InvalidOperationException("No se pudo encontrar el método estático 'Run'.");

                object returnValue = method.Invoke(null, null);

                result.Success = true;
                result.ReturnValue = SerializeReturnValue(returnValue);
            }
            else
            {
                result.Success = false;
                result.ErrorMessage = compilationErrors;
            }
        }
        catch (Exception e)
        {
            result.Success = false;
            result.ErrorMessage = $"[Execution Error] {e.GetType().Name}: {e.Message}\n{e.StackTrace}";
        }
        finally
        {
            Application.logMessageReceivedThreaded -= logHandler.HandleLog;
            result.ConsoleOutput = logHandler.GetLogs();
        }

        return result;
    }

    private static (Assembly, string) Compile(string code, List<string> additionalReferences)
    {
        var provider = new CSharpCodeProvider();
        var parameters = new CompilerParameters();
        
        var references = GetAssemblyReferences(additionalReferences);
        foreach (var assemblyPath in references)
        {
            parameters.ReferencedAssemblies.Add(assemblyPath);
        }

        parameters.GenerateInMemory = true;
        parameters.GenerateExecutable = false;

        string sourceCode = BuildSourceTemplate(code);
        CompilerResults results = provider.CompileAssemblyFromSource(parameters, sourceCode);

        if (results.Errors.HasErrors)
        {
            var errors = new StringBuilder();
            foreach (CompilerError error in results.Errors)
            {
                // Ajustamos el número de línea restando el offset de la plantilla de código
                errors.AppendLine($"Line {error.Line - 16}: {error.ErrorText}");
            }
            return (null, $"[Compilation Error]\n{errors}");
        }

        return (results.CompiledAssembly, null);
    }

    private static string BuildSourceTemplate(string code)
    {
        // El offset de línea es de 16 líneas (incluyendo la línea en blanco de arriba)
        return $@"
            using UnityEngine;
            using UnityEditor;
            using System;
            using System.IO;
            using System.Linq;
            using System.Reflection;
            using System.Collections;
            using System.Collections.Generic;

            public static class DynamicExecutor
            {{
                public static object Run()
                {{
                    {code}
                    return null;
                }}
            }}
        ";
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

    private static void InitializeAssemblyCache()
    {
        if (_assemblyCache != null) return;
        Debug.Log("[CSharpRunner] Inicializando caché de ensamblados...");
        _assemblyCache = AppDomain.CurrentDomain.GetAssemblies()
            .Where(a => !a.IsDynamic && !string.IsNullOrEmpty(a.Location))
            .ToDictionary(a => Path.GetFileName(a.Location), a => a.Location, StringComparer.OrdinalIgnoreCase);
        Debug.Log($"[CSharpRunner] Cacheados {_assemblyCache.Count} ensamblados.");
    }
    
    private static List<string> GetAssemblyReferences(List<string> additionalReferences)
    {
        InitializeAssemblyCache();

        var finalReferences = new HashSet<string>
        {
            // Siempre incluimos los ensamblados absolutamente esenciales
            _assemblyCache["mscorlib.dll"],
            _assemblyCache["System.dll"],
            _assemblyCache["System.Core.dll"],
            _assemblyCache["UnityEngine.dll"],
            _assemblyCache["UnityEditor.dll"]
        };

        if (additionalReferences != null)
        {
            foreach (var reference in additionalReferences)
            {
                if (_assemblyCache.TryGetValue(reference, out var path))
                {
                    finalReferences.Add(path);
                }
                else
                {
                    Debug.LogWarning($"[CSharpRunner] Referencia de ensamblado no encontrada en la caché: {reference}");
                }
            }
        }
        
        return finalReferences.ToList();
    }
    
    #endregion

    private static CommandResult TakeScreenshot()
    {
        try
        {
            string tempPath = Path.Combine(Path.GetTempPath(), "mcp_screenshot.png");
            ScreenCapture.CaptureScreenshot(tempPath, 1);
            System.Threading.Thread.Sleep(1000);

            if (!File.Exists(tempPath))
            {
                throw new Exception("La captura de pantalla no se pudo guardar en el disco.");
            }

            byte[] bytes = File.ReadAllBytes(tempPath);
            string base64 = Convert.ToBase64String(bytes);
            File.Delete(tempPath);

            return new CommandResult { Success = true, ReturnValue = base64, ConsoleOutput = "Screenshot taken successfully." };
        }
        catch (Exception e)
        {
            return new CommandResult { Success = false, ErrorMessage = $"[Screenshot Error] {e.GetType().Name}: {e.Message}" };
        }
    }
    
    private class LogHandler
    {
        private readonly StringBuilder _stringBuilder = new StringBuilder();
        public void HandleLog(string logString, string stackTrace, LogType type) { _stringBuilder.AppendLine($"[{type}] {logString}"); }
        public string GetLogs() => _stringBuilder.ToString();
    }
}