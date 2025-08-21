import requests
import base64
import json

MCP_BASE_URL = "http://127.0.0.1:8001"

def run_command(command: str):
    """Función helper para enviar un comando al servidor MCP."""
    print("-" * 50)
    print(f"▶️  Enviando comando: {command[:80]}...")
    try:
        response = requests.post(
            f"{MCP_BASE_URL}/unity/run-command",
            json={"command": command}
        )
        response.raise_for_status()
        result = response.json()
        
        if result.get("success"):
            print(f"✅ Éxito:")
            print(f"   Output: {result.get('output')}")
        else:
            print(f"❌ Error:")
            print(f"   Mensaje: {result.get('error')}")
        
        return result

    except requests.RequestException as e:
        print(f"🚨 ERROR DE CONEXIÓN: No se pudo conectar al servidor MCP en {MCP_BASE_URL}.")
        print(f"   Asegúrate de que el servidor FastAPI está en ejecución.")
        return None

if __name__ == "__main__":
    print("🚀 Iniciando Test de Integración End-to-End...")
    print("Asegúrate de que tanto el servidor MCP (Python) como el editor de Unity estén en ejecución.")

    # Test 1: Crear un GameObject en la escena
    run_command('new UnityEngine.GameObject("TestCubeFromAI");')

    # Test 2: Devolver información del editor
    run_command("return UnityEditor.EditorApplication.unityVersion;")

    # Test 3: Ejecutar un comando que provocará un error de compilación
    run_command('int x = "error";')

    # Test 4: Tomar una captura de pantalla y guardarla
    result = run_command("TAKE_SCREENSHOT")
    if result and result.get("success") and result.get("output"):
        print("🖼️  Procesando captura de pantalla...")
        try:
            image_data = base64.b64decode(result["output"])
            with open("screenshot.jpg", "wb") as f:
                f.write(image_data)
            print("✅ Captura de pantalla guardada como 'screenshot.jpg'.")
        except Exception as e:
            print(f"❌ Error al guardar la captura de pantalla: {e}")
            
    print("-" * 50)
    print("🏁 Test de Integración Finalizado.")