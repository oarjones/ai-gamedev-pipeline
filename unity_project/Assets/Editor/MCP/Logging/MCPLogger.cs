// MCPLogger.cs - Unified logger for Unity Editor side
using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using UnityEditor;
using UnityEngine;
using MCP.Logging;

namespace MCP.Logging
{
    /// <summary>
    /// Logger estructurado para el lado del Editor de Unity.
    /// Envía a la consola local y opcionalmente remite por WebSocket.
    /// </summary>
    public static class MCPLogger
    {
        public enum Level { DEBUG, INFO, WARNING, ERROR, CRITICAL }

        private static Level _minLevel = Level.INFO;
        private static string _component = "unity_editor";
        private static string _category = null;
        private static LogBuffer _buffer = new LogBuffer(1000);
        private static LogWebSocketClient _client = new LogWebSocketClient("ws://127.0.0.1:8765/ws/logs");
        private static CancellationTokenSource _cts = new CancellationTokenSource();

        /// <summary>
        /// Configura nivel mínimo, componente y URL de WebSocket opcional para envío.
        /// </summary>
        public static void Configure(Level minLevel, string component = null, string wsUrl = null)
        {
            _minLevel = minLevel;
            if (!string.IsNullOrEmpty(component)) _component = component;
            if (!string.IsNullOrEmpty(wsUrl)) _client = new LogWebSocketClient(wsUrl);
        }

        /// <summary>
        /// Establece una categoría opcional para agrupar eventos.
        /// </summary>
        public static void SetCategory(string category)
        {
            _category = category;
        }

        /// <summary>
        /// Registra un evento con nivel, mensaje y metadatos opcionales.
        /// </summary>
        public static void Log(Level level, string message, string module = "Unity", string correlationId = null, string stack = null, Dictionary<string, object> extra = null)
        {
            if (level < _minLevel) return;
            var entry = new LogEntry
            {
                timestamp = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.0,
                component = _component,
                level = level.ToString(),
                module = module,
                message = message,
                category = _category,
                correlation_id = correlationId,
                stack = stack,
                performance_ms = null,
                extra = extra ?? new Dictionary<string, object>()
            };

            // Local Unity console
            switch (level)
            {
                case Level.DEBUG:
                case Level.INFO:
                    Debug.Log(Format(entry)); break;
                case Level.WARNING:
                    Debug.LogWarning(Format(entry)); break;
                case Level.ERROR:
                case Level.CRITICAL:
                    Debug.LogError(Format(entry)); break;
            }

            // Buffer then try to ship
            _buffer.Enqueue(entry);
            EditorApplication.delayCall += TryFlush;
        }

        /// <summary>
        /// Registra una métrica de rendimiento con etiqueta y duración en ms.
        /// </summary>
        public static void LogPerformance(string label, double ms, string module = "Unity", string correlationId = null)
        {
            var extra = new Dictionary<string, object> { { "metric", label } };
            Log(Level.INFO, $"perf {label} {ms:F2}ms", module, correlationId, null, extra);
        }

        private static string Format(LogEntry e)
        {
            return $"{DateTimeOffset.FromUnixTimeMilliseconds((long)(e.timestamp*1000)).UtcDateTime:o} {e.component} {e.level} {e.module} {e.message}";
        }

        private static async void TryFlush()
        {
            if (!_client.CanSend()) return;
            foreach (var e in _buffer.Drain())
            {
                var json = JsonUtility.ToJson(new Wrapper { type = "log", payload = e });
                var ok = await _client.SendAsync(json, _cts.Token);
                if (!ok)
                {
                    // put back in buffer head-on failure
                    _buffer.Enqueue(e);
                    break;
                }
            }
        }

        [Serializable]
        private class Wrapper
        {
            public string type;
            public LogEntry payload;
        }
    }
}
