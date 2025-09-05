# Seguridad

- Transporte: WebSocket sobre localhost; considerar TLS si se expone fuera de la máquina local.
- Autorización: scoping por comando/herramienta y whitelists en Bridge.
- Validación de entrada: tipos estrictos, límites en payloads y timeouts.
- Aislamiento: ejecutar operaciones de alto riesgo en procesos/entornos separados cuando aplique.
- Logs: evitar datos sensibles; rotación y niveles configurables.

## Recomendaciones

- Usa puertos no estándar y restringe firewall a localhost cuando sea posible.
- Habilita autenticación por token si hay múltiples clientes.
- Añade pruebas de fuzzing para comandos críticos.

