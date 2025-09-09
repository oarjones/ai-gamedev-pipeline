// ValidationError.cs
// Simple model to represent results produced by validators.

namespace MCP.Validation
{
    /// <summary>
    /// Represents a validation finding produced by an <see cref="ICodeValidator"/>.
    /// </summary>
    public sealed class ValidationError
    {
        /// <summary>
        /// Human-readable message describing the issue.
        /// </summary>
        public string Message { get; set; }

        /// <summary>
        /// Optional 1-based line number where the issue occurs.
        /// </summary>
        public int? Line { get; set; }

        /// <summary>
        /// Optional 1-based column number where the issue occurs.
        /// </summary>
        public int? Column { get; set; }

        /// <summary>
        /// Severity classification for this finding.
        /// </summary>
        public ValidationSeverity Severity { get; set; }

        /// <summary>
        /// Optional code or identifier for the rule.
        /// </summary>
        public string Code { get; set; }

        /// <summary>
        /// Constructs a new instance.
        /// </summary>
        public ValidationError(
            string message,
            ValidationSeverity severity = ValidationSeverity.Error,
            int? line = null,
            int? column = null,
            string code = null)
        {
            Message = message;
            Severity = severity;
            Line = line;
            Column = column;
            Code = code;
        }
    }
}

