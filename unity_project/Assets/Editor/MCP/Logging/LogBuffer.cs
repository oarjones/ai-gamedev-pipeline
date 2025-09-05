// LogBuffer.cs - Unity side buffered queue for log entries
using System.Collections.Generic;

namespace MCP.Logging
{
    public class LogBuffer
    {
        private readonly Queue<LogEntry> _queue = new Queue<LogEntry>();
        private readonly int _max;

        public LogBuffer(int maxSize = 1000)
        {
            _max = maxSize;
        }

        public void Enqueue(LogEntry e)
        {
            _queue.Enqueue(e);
            while (_queue.Count > _max)
            {
                _queue.Dequeue();
            }
        }

        public IEnumerable<LogEntry> Drain()
        {
            while (_queue.Count > 0)
            {
                yield return _queue.Dequeue();
            }
        }
    }
}

