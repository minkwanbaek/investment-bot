from fastapi.testclient import TestClient

from investment_bot.main import app


client = TestClient(app)


def test_upbit_status_endpoint_reports_configured():
    response = client.get("/exchange/upbit/status")
    assert response.status_code == 200
    body = response.json()
    assert body["exchange"] == "upbit"
    assert "configured" in body
