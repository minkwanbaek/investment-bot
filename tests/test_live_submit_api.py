from fastapi.testclient import TestClient

from investment_bot.main import app


client = TestClient(app)


def test_submit_endpoint_stays_blocked_in_shadow_mode():
    response = client.post(
        "/exchange/upbit/orders/submit",
        json={
            "symbol": "BTC/KRW",
            "side": "buy",
            "price": 102913123,
            "volume": 0.001,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "blocked"
    assert body["reason"] in {"live_mode_disabled", "live_trading_not_confirmed", "order_below_exchange_rules"}
