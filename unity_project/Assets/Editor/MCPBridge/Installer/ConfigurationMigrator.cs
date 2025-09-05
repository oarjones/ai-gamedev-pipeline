using UnityEngine;
using System;

public static class ConfigurationMigrator
{
    public static void Migrate(Version from, Version to)
    {
        // TODO: Implement real migration using ScriptableObject config
        Debug.Log($"Migrating MCP config from {from} to {to}");
    }
}

