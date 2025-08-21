using Microsoft.CSharp;
using System;
using System.CodeDom.Compiler;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Text;
using UnityEditor;
using UnityEngine;

public static class CSharpRunner
{
    public static CommandResult Execute(string code)
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

            var assembly = CompileWithFallback(code, result); // Lógica de compilación mejorada
            if (assembly != null)
            {
                // Punto 2: Reflexión endurecida con null-checks
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
                // Punto 2: Serialización del ReturnValue mejorada
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
        // Punto 3: Intento 1 - Compilar con una lista reducida y esencial de ensamblados
        var essentialAssemblies = GetEssentialAssemblies();
        var (assembly, compilationErrors) = Compile(code, essentialAssemblies);

        if (assembly != null)
        {
            return assembly; // Éxito en el primer intento
        }

        // Si el primer intento falla, podría ser por una referencia faltante.
        // Intento 2 - Compilar con todos los ensamblados como fallback.
        Debug.LogWarning("[CSharpRunner] La compilación rápida falló, reintentando con todos los ensamblados...");
        var allAssemblies = GetAllAssemblies();
        var (fallbackAssembly, fallbackErrors) = Compile(code, allAssemblies);

        if(fallbackAssembly != null)
        {
            return fallbackAssembly;
        }

        // Si ambos fallan, devolvemos el error del intento más completo.
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

    // Punto 1: Solución al bug de la plantilla return
    private static string BuildSourceTemplate(string code)
    {
        // Esta plantilla ahora ejecuta siempre el código del usuario y devuelve null si no hay un return explícito.
        return $@"
            using UnityEngine;
            using UnityEditor;
            using System;
            using System.IO;
            using System.Linq;
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

        // Si es un objeto de Unity, devolvemos información clave en formato JSON.
        if (value is UnityEngine.Object unityObject)
        {
            return JsonUtility.ToJson(new {
                name = unityObject.name,
                type = unityObject.GetType().FullName,
                instanceID = unityObject.GetInstanceID()
            });
        }

        // Para tipos primitivos o serializables, usamos su string.
        return value.ToString();
    }

    #region Assembly Management

    private static IEnumerable<string> GetEssentialAssemblies()
    {
        // Lista curada para un rendimiento óptimo
        return new List<string>
        {
            "System.dll",
            "System.Core.dll",
            "System.Linq.dll",
            GetAssemblyPathByName("UnityEngine.CoreModule"),
            GetAssemblyPathByName("UnityEditor.CoreModule"),
            // Añade aquí otros ensamblados que se usen frecuentemente
        }.Where(p => !string.IsNullOrEmpty(p)).Distinct();
    }

    private static IEnumerable<string> GetAllAssemblies()
    {
        return AppDomain.CurrentDomain.GetAssemblies()
            .Where(a => !a.IsDynamic && !string.IsNullOrEmpty(a.Location))
            .Select(a => a.Location);
    }

    private static string GetAssemblyPathByName(string name)
    {
        return AppDomain.CurrentDomain.GetAssemblies()
            .FirstOrDefault(a => a.GetName().Name == name)?.Location;
    }

    #endregion

    private static CommandResult TakeScreenshot()
    {
        try
        {
            // Guardar la captura en un archivo temporal
            string tempPath = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "mcp_screenshot.png");
            ScreenCapture.CaptureScreenshot(tempPath, 1);

            // Esperar un poco para asegurarse de que el archivo se ha escrito en disco
            // (Esto es una medida de seguridad, puede no ser siempre necesario)
            System.Threading.Thread.Sleep(100);

            if (!System.IO.File.Exists(tempPath))
            {
                throw new Exception("La captura de pantalla no se pudo guardar en el disco.");
            }

            // Leer los bytes del archivo, convertirlos a Base64 y luego borrar el archivo
            byte[] bytes = System.IO.File.ReadAllBytes(tempPath);
            string base64 = Convert.ToBase64String(bytes);
            System.IO.File.Delete(tempPath);

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

    // Clase interna para capturar logs
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