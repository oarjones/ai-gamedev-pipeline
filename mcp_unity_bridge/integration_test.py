import requests
import base64
import json
from typing import List, Optional

MCP_BASE_URL = "http://127.0.0.1:8001"

def run_command(command: str, additional_assemblies: Optional[List[str]] = None):
    """Función helper para enviar un comando al servidor MCP."""
    print("-" * 50)
    
    # Construimos el payload
    payload = {"command": command}
    if additional_assemblies:
        payload["additional_references"] = additional_assemblies
        print(f"▶️  Enviando comando con ensamblados adicionales: {additional_assemblies}")
    else:
        print(f"▶️  Enviando comando: {command[:80].strip()}...")

    try:
        response = requests.post(
            f"{MCP_BASE_URL}/unity/run-command",
            json=payload
        )
        response.raise_for_status()
        result = response.json()
        
        if result.get("success"):
            print(f"✅ Éxito:")
            print(f"   Output: {result.get('output')}")
            # Añadimos el output de la consola de Unity si existe
            if result.get('console_output'):
                print(f"   Console: \n---\n{result.get('console_output').strip()}\n---")
        else:
            print(f"❌ Error:")
            print(f"   Mensaje: {result.get('error')}")
        
        return result

    except requests.RequestException as e:
        print(f"🚨 ERROR DE CONEXIÓN: No se pudo conectar al servidor MCP en {MCP_BASE_URL}.")
        print(f"   Asegúrate de que el servidor FastAPI está en ejecución.")
        return None

def save_screenshot(result, filename="screenshot.png"):
    """Función helper para decodificar y guardar una captura de pantalla."""
    if result and result.get("success") and result.get("output"):
        print(f"🖼️  Procesando captura de pantalla '{filename}'...")
        try:
            # Quitamos el prefijo si existe
            image_data_str = result["output"]
            if "," in image_data_str:
                image_data_str = image_data_str.split(',')[1]
            
            image_data = base64.b64decode(image_data_str)
            with open(filename, "wb") as f:
                f.write(image_data)
            print(f"✅ Captura de pantalla guardada como '{filename}'.")
        except Exception as e:
            print(f"❌ Error al guardar la captura de pantalla: {e}")

if __name__ == "__main__":
    print("🚀 Iniciando Test de Integración End-to-End...")
    print("Asegúrate de que tanto el servidor MCP (Python) como el editor de Unity estén en ejecución.")

    # # Test 1: Crear un GameObject en la escena
    # run_command('new UnityEngine.GameObject("TestCubeFromAI");')

    # # Test 2: Devolver información del editor
    # run_command("return UnityEngine.Application.version;")

    # # Test 3: Ejecutar un comando que provocará un error de compilación
    # run_command('int x = "error";')

    # # Test 4: Tomar una captura de pantalla y guardarla (escena vacía)
    # result_empty = run_command("TAKE_SCREENSHOT")
    # save_screenshot(result_empty, "screenshot_empty.png")
            
    # # Test 5: Usar un 'using' adicional para XML
    # xml_test_code = """
    # using System.Xml;
    # var doc = new XmlDocument();
    # doc.LoadXml("<item><name>test</name></item>");
    # return doc.SelectSingleNode("item/name").InnerText;
    # """
    # run_command(xml_test_code)

    # # Test 6: Añadir un ensamblado adicional (System.Xml.Linq) y usarlo.
    # xdocument_test_code = """
    # using System.Xml.Linq;
    # var doc = new XDocument(new XElement("root", new XElement("child", "content")));
    # return doc.Root.Element("child").Value;
    # """
    # run_command(xdocument_test_code, additional_assemblies=["System.Xml.Linq"])

    # Test 7: NUEVO - Crear una escena y tomar una captura para verificar
    print("\n--- INICIANDO TEST 7: CREACIÓN DE ESCENA Y CAPTURA ---")
    
    # Paso 1: Crear un cubo en el origen. Usamos CreatePrimitive para que tenga malla y renderer.
    run_command('var cube = UnityEngine.GameObject.CreatePrimitive(UnityEngine.PrimitiveType.Cube); cube.name = "TestCube";')
    
    # Paso 2: Crear una luz direccional para que la escena no se vea negra.
    light_command = """
    var lightGO = new UnityEngine.GameObject("TestLight");
    var light = lightGO.AddComponent<UnityEngine.Light>();
    light.type = UnityEngine.LightType.Directional;
    light.transform.rotation = UnityEngine.Quaternion.Euler(50, -30, 0);
    """
    run_command(light_command)
    
    # Paso 3: Tomar la captura de la escena con contenido.
    result_scene = run_command("TAKE_SCREENSHOT")
    save_screenshot(result_scene, "screenshot_with_scene.png")
            
    print("-" * 50)
    print("🏁 Test de Integración Finalizado.")