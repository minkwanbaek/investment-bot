from fastapi.testclient import TestClient

from investment_bot.main import app
from investment_bot.services.container import get_paper_broker


client = TestClient(app)


def setup_function():
    broker = get_paper_broker()
    broker.orders.clear()
    broker.positions.clear()
    broker.cash_balance = broker.starting_cash


def test_health_endpoint_exposes_runtime_config():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "paper"
    assert body["symbols"] == ["BTC/KRW"]


def test_config_endpoint_returns_loaded_settings():
    response = client.get("/config")
    assert response.status_code == 200
    body = response.json()
    assert body["starting_cash"] == 10_000_000
    assert body["enabled_strategies"] == ["dca", "mean_reversion", "trend_following"]


def test_portfolio_endpoint_returns_empty_snapshot():
    response = client.get("/paper/portfolio")
    assert response.status_code == 200
    body = response.json()
    assert body["order_count"] == 0
    assert body["positions"] == {}


def test_dry_run_cycle_records_order_for_buy_signal():
    response = client.post(
        "/cycle/dry-run",
        json={
            "strategy_name": "trend_following",
            "candles": [
                {"symbol": "BTC/KRW", "timeframe": "1h", "open": 1, "high": 1, "low": 1, "close": 100, "volume": 1, "timestamp": "1"},
                {"symbol": "BTC/KRW", "timeframe": "1h", "open": 1, "high": 1, "low": 1, "close": 101, "volume": 1, "timestamp": "2"},
                {"symbol": "BTC/KRW", "timeframe": "1h", "open": 1, "high": 1, "low": 1, "close": 102, "volume": 1, "timestamp": "3"},
                {"symbol": "BTC/KRW", "timeframe": "1h", "open": 1, "high": 1, "low": 1, "close": 103, "volume": 1, "timestamp": "4"},
                {"symbol": "BTC/KRW", "timeframe": "1h", "open": 1, "high": 1, "low": 1, "close": 104, "volume": 1, "timestamp": "5"},
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["signal"]["action"] == "buy"
    assert body["review"]["approved"] is True
    assert body["broker_result"]["status"] == "recorded"
    assert body["portfolio"]["order_count"] == 1
    assert body["portfolio"]["positions"]["BTC/KRW"] > 0


def test_dry_run_cycle_rejects_unknown_strategy():
    response = client.post(
        "/cycle/dry-run",
        json={
            "strategy_name": "unknown",
            "candles": [
                {"symbol": "BTC/KRW", "timeframe": "1h", "open": 1, "high": 1, "low": 1, "close": 100, "volume": 1, "timestamp": "1"}
            ],
        },
    )
    assert response.status_code == 400
    assert "unknown strategy" in response.json()["detail"]
