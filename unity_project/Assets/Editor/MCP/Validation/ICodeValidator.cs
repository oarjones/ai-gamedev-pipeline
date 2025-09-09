// ICodeValidator.cs
// Base infrastructure for C# code validation in Unity Editor.
// This interface defines the contract for pluggable validators.

using System.Collections.Generic;

namespace MCP.Validation
{
    /// <summary>
    /// Interface for pluggable C# code validators executed in the Unity Editor.
    /// Implementations should perform analysis on the provided source code and
    /// report any findings via <see cref="ValidationError"/> instances.
    /// </summary>
    public interface ICodeValidator
    {
        /// <summary>
        /// Validates the provided C# source code.
        /// </summary>
        /// <param name="code">Raw C# source code to validate.</param>
        /// <param name="errors">List of discovered validation errors (empty if none).</param>
        /// <returns>True if the code passes this validator, otherwise false.</returns>
        bool Validate(string code, out List<ValidationError> errors);

        /// <summary>
        /// Returns the default severity level this validator represents.
        /// This can be used to categorize validators or as a baseline for
        /// interpreting reported <see cref="ValidationError"/> entries.
        /// </summary>
        /// <returns>The validator severity classification.</returns>
        ValidationSeverity GetSeverity();

        /// <summary>
        /// Enables or disables this validator at runtime.
        /// </summary>
        bool IsEnabled { get; set; }
    }
}

