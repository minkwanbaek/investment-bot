from fastapi.testclient import TestClient

from investment_bot.main import app


client = TestClient(app)


def test_runs_reset_endpoint_clears_history():
    client.post("/runs/reset")
    response = client.get("/runs?limit=10")
    assert response.status_code == 200
    assert response.json()["runs"] == []


def test_runs_summary_endpoint_returns_empty_summary_after_reset():
    client.post("/runs/reset")
    response = client.get("/runs/summary?limit=10")
    assert response.status_code == 200
    body = response.json()
    assert body["total_runs"] == 0
    assert body["kind_counts"] == {}
    assert body["stop_reasons"] == {}
    assert body["latest_portfolio"] is None
