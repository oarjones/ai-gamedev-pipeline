from fastapi.testclient import TestClient
from mcp_unity_server.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "x-correlation-id" in response.headers

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

