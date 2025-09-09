// LogEntry.cs - Unity side structured log entry
using System;
using System.Collections.Generic;

namespace MCP.Logging
{
    [Serializable]
    public class LogEntry
    {
        public double timestamp;
        public string component;
        public string level;
        public string module;
        public string message;
        public string category;
        public string correlation_id;
        public string stack;
        public double? performance_ms;
        public Dictionary<string, object> extra;
    }
}

