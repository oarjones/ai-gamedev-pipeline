// LogBuffer.cs - Unity side buffered queue for log entries
using System.Collections.Generic;

namespace MCP.Logging
{
    /// <summary>
    /// Cola acotada para almacenar eventos de log antes de su envío.
    /// Desborda por cabeza cuando se supera el tamaño máximo.
    /// </summary>
    public class LogBuffer
    {
        private readonly Queue<LogEntry> _queue = new Queue<LogEntry>();
        private readonly int _max;

        /// <summary>
        /// Crea un buffer con capacidad máxima configurable.
        /// </summary>
        public LogBuffer(int maxSize = 1000)
        {
            _max = maxSize;
        }

        /// <summary>
        /// Encola una entrada y trunca si excede la capacidad.
        /// </summary>
        public void Enqueue(LogEntry e)
        {
            _queue.Enqueue(e);
            while (_queue.Count > _max)
            {
                _queue.Dequeue();
            }
        }

        /// <summary>
        /// Drena y devuelve las entradas encoladas en orden FIFO.
        /// </summary>
        public IEnumerable<LogEntry> Drain()
        {
            while (_queue.Count > 0)
            {
                yield return _queue.Dequeue();
            }
        }
    }
}
