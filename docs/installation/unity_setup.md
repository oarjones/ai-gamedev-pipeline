# Configuración de Unity

1. Abre `unity_project/` con Unity Hub (versión 2022.3 LTS recomendada).
2. Espera la importación inicial de paquetes (URP/VFX si aplica).
3. Verifica los scripts del Editor MCP en `Assets/Editor/MCP`:
   - `MCPWebSocketClient.cs`
   - `CommandDispatcher.cs`
   - `MCPToolbox.cs`
4. Ajusta la configuración de conexión (puerto/host) si tu Bridge no usa el predeterminado.
5. Abre `Window > AI GameDev > MCP Logs` (si existe) o la consola para verificar conexión.

## Compilación y permisos

- Asegúrate de tener permisos para conexiones WebSocket salientes.
- Si hay antivirus/firewall, permite `Unity.exe` y el puerto configurado del Bridge.

## Screenshots

Consulta la carpeta `Screenshot/` del repositorio para capturas de configuración del proyecto y la consola de conexión.

