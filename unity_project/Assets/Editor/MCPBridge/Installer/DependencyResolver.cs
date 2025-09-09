using UnityEditor;
using UnityEngine;

public static class DependencyResolver
{
    public static void CheckDependencies()
    {
        // Unity version
        var ver = Application.unityVersion;
        Debug.Log($"Unity version: {ver}");

        // Required packages
        InstallPackage("com.unity.nuget.newtonsoft-json");
        InstallPackage("com.unity.inputsystem");
    }

    private static void InstallPackage(string packageId)
    {
        UnityEditor.PackageManager.Client.Add(packageId);
    }
}

