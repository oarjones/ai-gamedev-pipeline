import requests
import base64
import json
from typing import List, Optional

MCP_BASE_URL = "http://127.0.0.1:8001"

def run_command(command: str, additional_assemblies: Optional[List[str]] = None):
    """Función helper para enviar un comando al servidor MCP."""
    print("-" * 50)
    
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

    # ... (Tests 1 al 6 se mantienen igual)
    # run_command('new UnityEngine.GameObject("TestCubeFromAI");')
    # run_command("return UnityEngine.Application.version;")
    # run_command('int x = "error";')
    # result_empty = run_command("TAKE_SCREENSHOT")
    # save_screenshot(result_empty, "screenshot_empty.png")
    # xml_test_code = 'using System.Xml; var doc = new XmlDocument(); doc.LoadXml("<item><name>test</name></item>"); return doc.SelectSingleNode("item/name").InnerText;'
    # run_command(xml_test_code)
    # xdocument_test_code = 'using System.Xml.Linq; var doc = new XDocument(new XElement("root", new XElement("child", "content"))); return doc.Root.Element("child").Value;'
    # run_command(xdocument_test_code, additional_assemblies=["System.Xml.Linq"])


    # Test 7: Crear una escena, ENCUADRAR el objeto, y tomar la captura
    print("\n--- INICIANDO TEST 7: CREACIÓN, ENCUADRE Y CAPTURA DE ESCENA ---")
    
    # Paso 1: Crear un cubo
    run_command('var cube = UnityEngine.GameObject.CreatePrimitive(UnityEngine.PrimitiveType.Cube); cube.name = "TestCube";')
    
    # Paso 2: Crear una luz direccional
    light_command = """
    var lightGO = new UnityEngine.GameObject("TestLight");
    var light = lightGO.AddComponent<UnityEngine.Light>();
    light.type = UnityEngine.LightType.Directional;
    light.transform.rotation = UnityEngine.Quaternion.Euler(50, -30, 0);
    """
    run_command(light_command)
    
    # Paso 3: NUEVO Y CRÍTICO - Encuadrar el cubo con la cámara de la escena
    frame_command = """
    var cube = UnityEngine.GameObject.Find("TestCube");
    if (cube != null) {
        var sceneView = UnityEditor.SceneView.lastActiveSceneView;
        if (sceneView != null) {
            sceneView.Frame(new UnityEngine.Bounds(cube.transform.position, UnityEngine.Vector3.one * 2), false);
        }
    }
    """
    run_command(frame_command)

    # Paso 4: Tomar la captura de la escena con el objeto ya encuadrado
    result_scene = run_command("TAKE_SCREENSHOT")
    save_screenshot(result_scene, "screenshot_with_scene.png")

    # Paso 5: NUEVO - Limpiar los objetos creados
    print("\n--- Limpiando escena del test ---")
    run_command('UnityEngine.Object.DestroyImmediate(UnityEngine.GameObject.Find("TestCube"));')
    run_command('UnityEngine.Object.DestroyImmediate(UnityEngine.GameObject.Find("TestLight"));')
            
    print("-" * 50)
    print("🏁 Test de Integración Finalizado.")