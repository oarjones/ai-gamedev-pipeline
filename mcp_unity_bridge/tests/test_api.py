from fastapi.testclient import TestClient
from mcp_unity_server.main import app

client = TestClient(app)

@pytest.fixture
def mock_requests_post():
    with patch("mcp_unity_server.main.requests.post") as mock_post:
        yield mock_post

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    
def test_run_unity_command():
    response = client.post("/unity/run-command", json={"command": "Debug.Log(\"Hello from test!\");"})
    assert response.status_code == 200
    json_response = response.json()
    assert json_response["success"] == True
    assert "recibido por el MCP" in json_response["output"]
    assert "x-correlation-id" in response.headers

def test_run_unity_command_with_correlation_id():
    headers = {"X-Correlation-ID": "test-id"}
    response = client.post("/unity/run-command", json={"command": "Debug.Log(\"Hello from test!\");"}, headers=headers)
    assert response.status_code == 200
    assert response.headers["x-correlation-id"] == "test-id"
    
def test_run_command_success(mock_requests_post):
    # Simula una respuesta exitosa del servidor de Unity
    mock_unity_response = {
        "Success": True,
        "ReturnValue": "10.0.0f1",
        "ErrorMessage": None
    }
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = json.dumps(mock_unity_response) # Unity devuelve un JSON string-encoded
    mock_requests_post.return_value = mock_response

    # Llama a nuestro endpoint
    response = client.post("/unity/run-command", json={"command": "return UnityEditor.EditorApplication.unityVersion;"})
    
    # Verifica
    assert response.status_code == 200
    json_response = response.json()
    assert json_response["success"] is True
    assert json_response["output"] == "10.0.0f1"
    assert json_response["error"] is None

def test_run_command_unity_error(mock_requests_post):
    # Simula una respuesta con error de compilación desde Unity
    mock_unity_response = {
        "Success": False,
        "ReturnValue": None,
        "ErrorMessage": "[Compilation Error] Line 1: Some C# error"
    }
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = json.dumps(mock_unity_response)
    mock_requests_post.return_value = mock_response

    response = client.post("/unity/run-command", json={"command": "int x = 'error';" })
    
    assert response.status_code == 200
    json_response = response.json()
    assert json_response["success"] is False
    assert "[Compilation Error]" in json_response["error"]

def test_run_command_connection_error(mock_requests_post):
    # Simula un fallo de conexión (ej. Unity no está abierto)
    from requests.exceptions import ConnectionError
    mock_requests_post.side_effect = ConnectionError("Failed to connect to host")

    response = client.post("/unity/run-command", json={"command": "irrelevant"})
    
    assert response.status_code == 200
    json_response = response.json()
    assert json_response["success"] is False
    assert "Error de comunicación con el editor de Unity" in json_response["error"]

