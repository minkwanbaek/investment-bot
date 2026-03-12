from fastapi.testclient import TestClient

import investment_bot.api.routes as routes
from investment_bot.main import app


client = TestClient(app)


class FakeLiveExecutionService:
    def submit_order(self, symbol: str, side: str, price: float, volume: float) -> dict:
        return {
            "status": "blocked",
            "reason": "live_mode_disabled",
            "symbol": symbol,
            "side": side,
            "price": price,
            "volume": volume,
        }


def test_submit_endpoint_stays_blocked_in_shadow_mode(monkeypatch):
    monkeypatch.setattr(routes, "get_live_execution_service", lambda: FakeLiveExecutionService())
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
    assert body["reason"] in {"live_mode_disabled", "live_trading_not_confirmed", "order_below_exchange_rules_or_balance"}
