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

            var assembly = CompileWithFallback(code, result);
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

    private static Assembly CompileWithFallback(string code, CommandResult result)
    {
        var essentialAssemblies = GetEssentialAssemblies();
        Debug.Log($"[CSharpRunner] Intentando compilación rápida con {essentialAssemblies.Count} ensamblados.");
        LogAssemblies(essentialAssemblies);
        var (assembly, compilationErrors) = Compile(code, essentialAssemblies);

        if (assembly != null)
        {
            return assembly;
        }

        Debug.LogWarning($"[CSharpRunner] La compilación rápida falló. Reintentando con todos los ensamblados. Error original:\n{compilationErrors}");
        var allAssemblies = GetAllAssemblies();
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

        foreach (var assemblyPath in referencedAssemblies)
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
                errors.AppendLine($"Line {error.Line}: {error.ErrorText}");
            }
            return (null, $"[Compilation Error]\n{errors.ToString()}");
        }

        return (results.CompiledAssembly, null);
    }

    private static string BuildSourceTemplate(string code)
    {
        return $@"
            using UnityEngine;
            using UnityEditor;
            using System;
            using System.IO;
            using System.Linq;
            using System.Collections.Generic;
            using System.Reflection;

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
            return JsonUtility.ToJson(new
            {
                name = unityObject.name,
                type = unityObject.GetType().FullName,
                instanceID = unityObject.GetInstanceID()
            });
        }

        return value.ToString();
    }

    #region Assembly Management

    private static List<string> GetEssentialAssemblies()
    {
        // Lista curada de los ensamblados más comunes para un rendimiento óptimo
        return new List<string>
        {
            //typeof(object).Assembly.Location, // mscorlib.dll
            //typeof(Uri).Assembly.Location, // System.dll
            typeof(System.Linq.Enumerable).Assembly.Location, // System.Core.dll
            typeof(System.Xml.XmlDocument).Assembly.Location, // System.Xml.dll
            typeof(UnityEngine.GameObject).Assembly.Location,
            typeof(UnityEditor.Editor).Assembly.Location,
        }.Distinct().ToList();
    }

    private static List<string> GetAllAssemblies()
    {
        // Lógica mejorada para filtrar ensamblados del sistema en conflicto
        return AppDomain.CurrentDomain.GetAssemblies()
            .Where(a => !a.IsDynamic && !string.IsNullOrEmpty(a.Location))
            .Where(a => !a.FullName.StartsWith("System") && !a.FullName.StartsWith("mscorlib"))
            .Select(a => a.Location)
            .Concat(GetEssentialAssemblies()) // Añadimos la lista esencial para asegurarnos de tener las bases
            .Distinct()
            .ToList();
    }

    private static void LogAssemblies(List<string> assemblies)
    {
        var logBuilder = new StringBuilder("Usando los siguientes ensamblados para la compilación:\n");
        foreach (var asm in assemblies)
        {
            logBuilder.AppendLine($"- {Path.GetFileName(asm)}");
        }
        Debug.Log(logBuilder.ToString());
    }

    #endregion

    private static CommandResult TakeScreenshot()
    {
        try
        {
            string tempPath = Path.Combine(Path.GetTempPath(), "mcp_screenshot.png");
            Debug.Log($"[CSharpRunner] Guardando captura en: {tempPath}");

            ScreenCapture.CaptureScreenshot(tempPath, 1);

            System.Threading.Thread.Sleep(500);

            if (!File.Exists(tempPath))
            {
                throw new Exception("La captura de pantalla no se pudo guardar en el disco. El archivo no se encontró después de esperar.");
            }

            byte[] bytes = File.ReadAllBytes(tempPath);
            string base64 = Convert.ToBase64String(bytes);
            File.Delete(tempPath);

            return new CommandResult
            {
                Success = true,
                ReturnValue = base64,
                ConsoleOutput = "Screenshot taken successfully."
            };
        }
        catch (Exception e)
        {
            return new CommandResult
            {
                Success = false,
                ErrorMessage = $"[Screenshot Error] {e.GetType().Name}: {e.Message}"
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