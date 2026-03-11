from fastapi.testclient import TestClient

from investment_bot.main import app


client = TestClient(app)


def test_runs_reset_endpoint_clears_history():
    client.post("/runs/reset")
    response = client.get("/runs?limit=10")
    assert response.status_code == 200
    assert response.json()["runs"] == []
