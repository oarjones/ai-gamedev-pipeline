// ValidationSeverity.cs
// Classification for validator severity levels and errors.

namespace MCP.Validation
{
    /// <summary>
    /// Severity classification used to describe validator criticality and
    /// individual error importance.
    /// </summary>
    public enum ValidationSeverity
    {
        Info = 0,
        Warning = 1,
        Error = 2,
        Critical = 3,
    }
}

