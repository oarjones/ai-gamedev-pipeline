// En: Assets/Editor/MCP/CSharpRunner.cs

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
using Newtonsoft.Json;

public static class CSharpRunner
{

    public static CommandExecutionResult Execute(string code, List<string> additionalReferences)
    {
        var result = new CommandExecutionResult();
        try
        {
            var (assembly, compilationErrors) = CompileWithFallback(code, result, additionalReferences);

            if (assembly != null)
            {
                var type = assembly.GetType("DynamicExecutor");
                if (type == null) throw new InvalidOperationException("No se pudo encontrar el tipo 'DynamicExecutor'.");

                var method = type.GetMethod("Run", BindingFlags.Public | BindingFlags.Static);
                if (method == null) throw new InvalidOperationException("No se pudo encontrar el método estático 'Run'.");

                object returnValue = method.Invoke(null, null);

                result.success = true;
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

    private static (Assembly, string) CompileWithFallback(string code, CommandExecutionResult result, List<string> additionalReferences)
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
        if (value == null)
        {
            return "null";
        }

        if (value is UnityEngine.Object unityObject)
        {
            return JsonConvert.SerializeObject(new { 
                name = unityObject.name, 
                type = unityObject.GetType().FullName, 
                instanceID = unityObject.GetInstanceID() 
            });
        }

        var valueType = value.GetType();
        if (valueType.IsPrimitive || value is string)
        {
            return value.ToString();
        }

        try
        {
            return JsonConvert.SerializeObject(value, new JsonSerializerSettings
            {
                ReferenceLoopHandling = ReferenceLoopHandling.Ignore,
                ContractResolver = new UnityContractResolver()
            });
        }
        catch (Exception e)
        {
            Debug.LogWarning($"[CSharpRunner] Error de serialización con Newtonsoft.Json: {e.Message}. Volviendo a ToString().");
            return value.ToString();
        }
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

    #endregion
}
