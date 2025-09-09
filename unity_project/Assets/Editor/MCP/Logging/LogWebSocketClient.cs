// LogWebSocketClient.cs - Unity WebSocket client for log shipping
using System;
using System.Net.WebSockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;

namespace MCP.Logging
{
    /// <summary>
    /// Cliente WebSocket minimal para remitir registros estructurados.
    /// Incluye backoff simple por enfriamiento tras fallos consecutivos.
    /// </summary>
    public class LogWebSocketClient
    {
        private readonly Uri _uri;
        private ClientWebSocket _ws;
        private DateTime _openUntil = DateTime.MinValue;
        private int _failures = 0;
        private readonly int _threshold = 3;
        private readonly TimeSpan _cooldown = TimeSpan.FromSeconds(15);

        /// <summary>
        /// Construye el cliente apuntando a la URL del servidor de logs.
        /// </summary>
        public LogWebSocketClient(string url)
        {
            _uri = new Uri(url);
            _ws = new ClientWebSocket();
        }

        /// <summary>
        /// Indica si se puede intentar enviar en este momento (no en cooldown).
        /// </summary>
        public bool CanSend()
        {
            return DateTime.UtcNow >= _openUntil;
        }

        private void RecordFailure()
        {
            _failures++;
            if (_failures >= _threshold)
            {
                _openUntil = DateTime.UtcNow + _cooldown;
                _failures = 0;
            }
        }

        private void RecordSuccess()
        {
            _failures = 0;
            _openUntil = DateTime.MinValue;
        }

        /// <summary>
        /// Envía un mensaje JSON por WebSocket, gestionando reconexión y fallos.
        /// </summary>
        public async Task<bool> SendAsync(string json, CancellationToken ct)
        {
            if (!CanSend()) return false;
            try
            {
                if (_ws.State != WebSocketState.Open)
                {
                    if (_ws.State != WebSocketState.None)
                        _ws.Dispose();
                    _ws = new ClientWebSocket();
                    await _ws.ConnectAsync(_uri, ct);
                }
                var bytes = Encoding.UTF8.GetBytes(json);
                await _ws.SendAsync(new ArraySegment<byte>(bytes), WebSocketMessageType.Text, true, ct);
                RecordSuccess();
                return true;
            }
            catch (Exception)
            {
                try { if (_ws != null) _ws.Dispose(); } catch {}
                RecordFailure();
                return false;
            }
        }
    }
}
