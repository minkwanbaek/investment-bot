from fastapi.testclient import TestClient

from investment_bot.main import app


client = TestClient(app)


def test_live_market_test_endpoint_rejects_unsupported_timeframe():
    response = client.get("/market-data/live/test?symbol=BTC/KRW&timeframe=2h&limit=3")
    assert response.status_code == 400
    assert "unsupported live timeframe" in response.json()["detail"]
