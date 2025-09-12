# En: mcp_unity_bridge/unity_tools.py

import json
from typing import Any
from bridges.mcp_adapter import send_to_unity_and_get_response, log, mcp

# Reutilizamos la instancia ``mcp`` creada en ``mcp_adapter`` para registrar
# las herramientas en el mismo servidor. Crear una nueva instancia aquí
# impediría que las tools se expusieran correctamente.

@mcp.tool()
async def create_gameobject(name: str) -> str:
    """
    Crea un nuevo GameObject vacío en la escena de Unity.

    Args:
        name: El nombre para el nuevo GameObject.

    Returns:
        Una cadena JSON con la respuesta de Unity, que incluye el instanceId del objeto creado.
    """
    log.info(f"Executing tool: create_gameobject with name '{name}'")
    # El payload debe ser un string JSON, como define models.py
    payload_dict = {"name": name}
    message = {
        "type": "tool",
        "action": "CreateGameObject",
        "payload": json.dumps(payload_dict)
    }
    response = await send_to_unity_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)

@mcp.tool()
async def find_gameobject(name: str) -> str:
    """
    Busca un GameObject en la escena por su nombre.

    Args:
        name: El nombre del GameObject a buscar.

    Returns:
        Una cadena JSON con la respuesta de Unity, incluyendo el instanceId o -1 si no se encuentra.
    """
    log.info(f"Executing tool: find_gameobject with name '{name}'")
    payload_dict = {"name": name}
    message = {
        "type": "tool",
        "action": "FindGameObject",
        "payload": json.dumps(payload_dict)
    }
    response = await send_to_unity_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)

@mcp.tool()
async def add_component(instanceId: int, componentType: str) -> str:
    """
    Añade un componente a un GameObject existente en Unity.

    Args:
        instanceId: El ID de instancia del GameObject.
        componentType: El nombre completo del tipo del componente (ej: "UnityEngine.Rigidbody").

    Returns:
        Una cadena JSON con la respuesta de Unity.
    """
    log.info(f"Executing tool: add_component of type '{componentType}' to object {instanceId}")
    payload_dict = {
        "instanceId": instanceId,
        "componentType": componentType
    }
    message = {
        "type": "tool",
        "action": "AddComponent",
        "payload": json.dumps(payload_dict)
    }
    response = await send_to_unity_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)

@mcp.tool()
async def set_component_property(instanceId: int, componentType: str, propertyName: str, value: Any) -> str:
    """
    Establece el valor de una propiedad en un componente de un GameObject.

    Args:
        instanceId: El ID de instancia del GameObject.
        componentType: El nombre completo del tipo del componente.
        propertyName: El nombre de la propiedad a modificar.
        value: El nuevo valor (puede ser un primitivo como string/int/float, o un dict para vectores/colores).

    Returns:
        Una cadena JSON con la respuesta de Unity.
    """
    log.info(f"Executing tool: set_component_property '{propertyName}' on '{componentType}' for object {instanceId}")
    payload_dict = {
        "instanceId": instanceId,
        "componentType": componentType,
        "propertyName": propertyName,
        "value": value
    }
    message = {
        "type": "tool",
        "action": "SetComponentProperty",
        "payload": json.dumps(payload_dict)
    }
    response = await send_to_unity_and_get_response(message)
    return json.dumps(response, indent=2, ensure_ascii=False)
