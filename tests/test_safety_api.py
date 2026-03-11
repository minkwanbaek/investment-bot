from fastapi.testclient import TestClient

from investment_bot.main import app


client = TestClient(app)


def test_semi_live_batch_rejects_invalid_iterations():
    response = client.post(
        "/cycle/semi-live/batch",
        json={
            "strategy_name": "trend_following",
            "symbol": "BTC/KRW",
            "timeframe": "1h",
            "limit": 5,
            "iterations": 0,
            "interval_seconds": 0,
        },
    )
    assert response.status_code == 422
