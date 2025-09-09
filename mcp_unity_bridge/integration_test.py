# En: mcp_unity_bridge/integration_test.py

import asyncio
import websockets
import json
import base64
import os
import pytest
try:
    from src.config_manager import ConfigManager  # type: ignore
except Exception:
    ConfigManager = None  # type: ignore

# --- CONFIGURACIÓN PARA EL TEST REAL ---
# Usamos el puerto 8001, que es el que tienes en tu config.py
if ConfigManager is not None:
    _cfg = ConfigManager().get()
    WEBSOCKET_BASE_URI = f"ws://{_cfg.servers.mcp_bridge.host}:{_cfg.servers.mcp_bridge.port}/ws/"
else:
    WEBSOCKET_BASE_URI = "ws://127.0.0.1:8001/ws/"
# Este es el ID de nuestro cliente de test, que simula ser el agente IA
AI_CLIENT_ID = "ai_agent_tester"
TIMEOUT = 15  # Aumentamos el timeout a 15s por si Unity tarda en procesar

@pytest.mark.asyncio
async def test_query_scene_hierarchy_real():
    """
    Test de integración REAL:
    1. Conecta un cliente IA al servidor.
    2. Envía una query para obtener la jerarquía de la escena.
    3. Espera la respuesta REAL que el Editor de Unity envía de vuelta.
    4. Valida que la respuesta es correcta.
    """
    print("\n--- INICIANDO TEST: 'test_query_scene_hierarchy_real' ---")
    print("Asegúrate de que el servidor FastAPI está corriendo y Unity está en modo Play.")

    async with websockets.connect(f"{WEBSOCKET_BASE_URI}{AI_CLIENT_ID}") as ai_ws:
        print(f"[TestAI] Conectado al servidor como '{AI_CLIENT_ID}'.")

        # 1. Preparar y enviar la query
        query_message = {
            "type": "query",
            "action": "get_scene_hierarchy",
            "payload": "{}" # Payload vacío para esta query
        }
        print(f"[TestAI->MCP] Enviando petición: {query_message}")
        await ai_ws.send(json.dumps(query_message))

        # 2. Esperar la respuesta de vuelta desde Unity
        print("[TestAI] Esperando respuesta del servidor (que viene de Unity)...")
        try:
            response_str = await asyncio.wait_for(ai_ws.recv(), timeout=TIMEOUT)
            response_data = json.loads(response_str)
            print(f"[MCP->TestAI] Respuesta recibida: {json.dumps(response_data, indent=2)}")

            # 3. Validar la respuesta
            assert response_data["status"] == "success"
            payload = json.loads(response_data["payload"])
            assert "data" in payload
            # La escena por defecto de Unity siempre tiene una cámara
            assert len(payload["data"]) > 0
            camera_found = any(item["name"] == "Main Camera" for item in payload["data"])
            assert camera_found, "No se encontró la 'Main Camera' en la jerarquía de la escena."
            print("--- TEST COMPLETADO CON ÉXITO ---")

        except asyncio.TimeoutError:
            pytest.fail(f"Timeout: No se recibió respuesta de Unity en {TIMEOUT} segundos.")
        except Exception as e:
            pytest.fail(f"El test falló con una excepción: {e}")


@pytest.mark.asyncio
async def test_command_create_cube_real():
    """
    Test de integración REAL para un comando que modifica la escena.
    """
    print("\n--- INICIANDO TEST: 'test_command_create_cube_real' ---")
    print("Este test creará un cubo llamado 'TestCube' en tu escena de Unity.")

    async with websockets.connect(f"{WEBSOCKET_BASE_URI}{AI_CLIENT_ID}") as ai_ws:
        print(f"[TestAI] Conectado al servidor como '{AI_CLIENT_ID}'.")

        # 1. Preparar y enviar el comando
        create_cube_code = 'var cube = GameObject.CreatePrimitive(PrimitiveType.Cube); cube.name = "TestCube"; return cube.name;'
        command_message = {
            "type": "command",
            "payload": json.dumps({
                "code": create_cube_code,
                "additional_references": []
            })
        }
        print(f"[TestAI->MCP] Enviando comando: {command_message}")
        await ai_ws.send(json.dumps(command_message))

        # 2. Esperar la respuesta de Unity
        print("[TestAI] Esperando respuesta del servidor...")
        try:
            response_str = await asyncio.wait_for(ai_ws.recv(), timeout=TIMEOUT)
            response_data = json.loads(response_str)
            print(f"[MCP->TestAI] Respuesta recibida: {json.dumps(response_data, indent=2)}")

            # 3. Validar la respuesta
            assert response_data["status"] == "success"
            payload = json.loads(response_data["payload"])
            assert payload["success"] is True
            # Unity serializa los strings de retorno con comillas dobles
            assert 'TestCube' in payload["output"]
            print("--- TEST COMPLETADO CON ÉXITO ---")
            print("Verifica que el cubo 'TestCube' ha aparecido en la jerarquía de tu escena en Unity.")

        except asyncio.TimeoutError:
            pytest.fail(f"Timeout: No se recibió respuesta de Unity en {TIMEOUT} segundos.")

@pytest.mark.asyncio
async def test_screenshot_command_real():
    """
    Test de integración REAL para el comando de captura de pantalla.
    """
    print("\n--- INICIANDO TEST: 'test_screenshot_command_real' ---")
    print("Este test solicitará una captura de pantalla a Unity y la guardará como 'test_screenshot.png'.")

    async with websockets.connect(f"{WEBSOCKET_BASE_URI}{AI_CLIENT_ID}") as ai_ws:
        print(f"[TestAI] Conectado al servidor como '{AI_CLIENT_ID}'.")

        # 1. Preparar y enviar el comando especial de captura de pantalla
        command_message = {
            "type": "command",
            "payload": json.dumps({
                "code": "TAKE_SCREENSHOT",
                "additional_references": []
            })
        }
        print(f"[TestAI->MCP] Enviando comando: {command_message}")
        await ai_ws.send(json.dumps(command_message))

        # 2. Esperar la respuesta de Unity
        print("[TestAI] Esperando respuesta del servidor...")
        try:
            response_str = await asyncio.wait_for(ai_ws.recv(), timeout=TIMEOUT)
            response_data = json.loads(response_str)
            print(f"[MCP->TestAI] Respuesta recibida con éxito.")

            # 3. Validar la respuesta
            assert response_data["status"] == "success"
            payload = json.loads(response_data["payload"])
            assert payload["success"] is True
            assert payload["error"] is None

            # 4. Comprobar que la salida es una imagen PNG válida en base64
            output_base64 = payload["output"]
            assert output_base64 is not None, "La salida de la captura de pantalla no puede ser nula."

            image_data = base64.b64decode(output_base64)
            # La cabecera de un fichero PNG siempre empieza con estos 8 bytes
            is_png = image_data.startswith(b'\x89PNG\r\n\x1a\n')
            assert is_png, "La respuesta no es una imagen PNG válida."

            # Opcional: Guardar la imagen para verificarla manualmente
            output_path = "test_screenshot.png"
            with open(output_path, "wb") as f:
                f.write(image_data)
            print(f"Screenshot guardada en: {os.path.abspath(output_path)}")

            print("--- TEST COMPLETADO CON ÉXITO ---")

        except asyncio.TimeoutError:
            pytest.fail(f"Timeout: No se recibió respuesta de Unity en {TIMEOUT} segundos.")
        except Exception as e:
            pytest.fail(f"El test falló con una excepción: {e}")
