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
            // Capturar logs de Unity
            Application.logMessageReceived += logHandler.HandleLog;

            var assembly = Compile(code, result);
            if (assembly != null)
            {
                var type = assembly.GetType("DynamicExecutor");
                var method = type.GetMethod("Run");
                object returnValue = method.Invoke(null, null);

                result.Success = true;
                result.ReturnValue = returnValue?.ToString() ?? "null";
            }
        }
        catch (Exception e)
        {
            result.Success = false;
            result.ErrorMessage = $"[Execution Error] {e.GetType().Name}: {e.Message}\n{e.StackTrace}";
        }
        finally
        {
            // Dejar de capturar logs
            Application.logMessageReceived -= logHandler.HandleLog;
            result.ConsoleOutput = stringBuilder.ToString();
        }

        return result;
    }

    private static Assembly Compile(string code, CommandResult result)
    {
        var provider = new CSharpCodeProvider();
        var parameters = new CompilerParameters();

        // Añadir referencias a ensamblados de Unity
        foreach (var assembly in AppDomain.CurrentDomain.GetAssemblies())
        {
            if (assembly.IsDynamic) continue;
            try
            {
                if (!string.IsNullOrEmpty(assembly.Location))
                {
                    parameters.ReferencedAssemblies.Add(assembly.Location);
                }
            }
            catch (NotSupportedException) { /* Ignorar ensamblados en memoria */ }
        }
        
        parameters.GenerateInMemory = true;
        parameters.GenerateExecutable = false;

        string sourceCode = BuildSourceTemplate(code);
        CompilerResults results = provider.CompileAssemblyFromSource(parameters, sourceCode);

        if (results.Errors.HasErrors)
        {
            result.Success = false;
            var errors = new StringBuilder();
            foreach (CompilerError error in results.Errors)
            {
                errors.AppendLine($"Line {error.Line}: {error.ErrorText}");
            }
            result.ErrorMessage = $"[Compilation Error]\n{errors.ToString()}";
            return null;
        }

        return results.CompiledAssembly;
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

            public static class DynamicExecutor
            {{
                public static object Run()
                {{
                    {(code.Contains("return") ? "" : "return null;")}
                    {code}
                }}
            }}
        ";
    }

    private static CommandResult TakeScreenshot()
    {
        try
        {
            var texture = ScreenCapture.CaptureScreenshotAsTexture();
            byte[] bytes = ImageConversion.EncodeToJPG(texture, 75);
            UnityEngine.Object.DestroyImmediate(texture); // Limpiar memoria
            string base64 = Convert.ToBase64String(bytes);

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
                ErrorMessage = $"[Screenshot Error] {e.Message}"
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