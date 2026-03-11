from pathlib import Path

from fastapi.testclient import TestClient

from investment_bot.main import app
from investment_bot.services.container import get_market_data_service, get_paper_broker, get_run_history_service


client = TestClient(app)


def setup_function():
    broker = get_paper_broker()
    broker.orders.clear()
    broker.positions.clear()
    broker.last_prices.clear()
    broker.cash_balance = broker.starting_cash
    broker.total_realized_pnl = 0.0
    if broker.ledger_store:
        broker.ledger_store.path.unlink(missing_ok=True)
        broker._persist_state()

    market_data_service = get_market_data_service()
    if market_data_service.candle_store:
        market_data_service.candle_store.store.path.unlink(missing_ok=True)
    mock_adapter = market_data_service.registry.get("mock")
    replay_adapter = market_data_service.registry.get("replay")
    mock_adapter._series.clear()
    replay_adapter._series.clear()
    replay_adapter._cursor.clear()

    run_history_service = get_run_history_service()
    run_history_service.reset()


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


def test_config_validation_endpoint_returns_valid_result():
    response = client.get("/config/validate")
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["issues"] == []


def test_portfolio_endpoint_returns_empty_snapshot():
    response = client.get("/paper/portfolio")
    assert response.status_code == 200
    body = response.json()
    assert body["portfolio"]["order_count"] == 0
    assert body["portfolio"]["positions"] == {}
    assert body["portfolio"]["total_realized_pnl"] == 0
    assert body["portfolio"]["total_unrealized_pnl"] == 0
    assert body["alerts"] == []


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
    assert body["broker_result"]["order"]["requested_price"] == 104
    assert body["broker_result"]["order"]["execution_price"] > 104
    assert body["broker_result"]["order"]["fee_pct"] == 0.05
    assert body["portfolio"]["order_count"] == 1
    assert body["portfolio"]["positions"]["BTC/KRW"]["quantity"] > 0
    assert body["portfolio"]["positions"]["BTC/KRW"]["average_price"] == 104


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


def test_market_data_adapter_flow_runs_cycle_from_seeded_mock_data():
    candles = [
        {"symbol": "BTC/KRW", "timeframe": "1h", "open": 1, "high": 1, "low": 1, "close": 100, "volume": 1, "timestamp": "1"},
        {"symbol": "BTC/KRW", "timeframe": "1h", "open": 1, "high": 1, "low": 1, "close": 101, "volume": 1, "timestamp": "2"},
        {"symbol": "BTC/KRW", "timeframe": "1h", "open": 1, "high": 1, "low": 1, "close": 102, "volume": 1, "timestamp": "3"},
        {"symbol": "BTC/KRW", "timeframe": "1h", "open": 1, "high": 1, "low": 1, "close": 103, "volume": 1, "timestamp": "4"},
        {"symbol": "BTC/KRW", "timeframe": "1h", "open": 1, "high": 1, "low": 1, "close": 104, "volume": 1, "timestamp": "5"},
    ]
    seed_response = client.post(
        "/market-data/mock/seed",
        json={
            "symbol": "BTC/KRW",
            "timeframe": "1h",
            "candles": candles,
        },
    )
    assert seed_response.status_code == 200

    run_response = client.post(
        "/cycle/from-adapter",
        json={
            "strategy_name": "trend_following",
            "adapter_name": "mock",
            "symbol": "BTC/KRW",
            "timeframe": "1h",
            "limit": 5,
        },
    )
    assert run_response.status_code == 200
    body = run_response.json()
    assert body["adapter"] == "mock"
    assert body["signal"]["action"] == "buy"
    assert body["portfolio"]["order_count"] == 1


def test_replay_backtest_endpoint_runs_multi_step_summary():
    candles = [
        {"symbol": "BTC/KRW", "timeframe": "1h", "open": 1, "high": 1, "low": 1, "close": 100, "volume": 1, "timestamp": "1"},
        {"symbol": "BTC/KRW", "timeframe": "1h", "open": 1, "high": 1, "low": 1, "close": 101, "volume": 1, "timestamp": "2"},
        {"symbol": "BTC/KRW", "timeframe": "1h", "open": 1, "high": 1, "low": 1, "close": 102, "volume": 1, "timestamp": "3"},
        {"symbol": "BTC/KRW", "timeframe": "1h", "open": 1, "high": 1, "low": 1, "close": 103, "volume": 1, "timestamp": "4"},
        {"symbol": "BTC/KRW", "timeframe": "1h", "open": 1, "high": 1, "low": 1, "close": 104, "volume": 1, "timestamp": "5"},
        {"symbol": "BTC/KRW", "timeframe": "1h", "open": 1, "high": 1, "low": 1, "close": 105, "volume": 1, "timestamp": "6"},
        {"symbol": "BTC/KRW", "timeframe": "1h", "open": 1, "high": 1, "low": 1, "close": 106, "volume": 1, "timestamp": "7"},
    ]
    load_response = client.post(
        "/market-data/replay/load",
        json={
            "symbol": "BTC/KRW",
            "timeframe": "1h",
            "candles": candles,
        },
    )
    assert load_response.status_code == 200

    run_response = client.post(
        "/backtest/replay",
        json={
            "strategy_name": "trend_following",
            "symbol": "BTC/KRW",
            "timeframe": "1h",
            "window": 5,
            "steps": 2,
        },
    )
    assert run_response.status_code == 200
    body = run_response.json()
    assert body["steps"] == 2
    assert len(body["runs"]) == 2
    assert body["runs"][0]["timestamp"] == "5"
    assert body["metrics"]["total_steps"] == 2
    assert body["metrics"]["equity_curve"][0] == 10000000
    assert "profit_factor" in body["metrics"]
    assert "return_pct" in body["metrics"]


def test_stored_market_data_endpoint_returns_persisted_candles():
    candles = [
        {"symbol": "BTC/KRW", "timeframe": "1h", "open": 1, "high": 1, "low": 1, "close": 100, "volume": 1, "timestamp": "1"},
        {"symbol": "BTC/KRW", "timeframe": "1h", "open": 1, "high": 1, "low": 1, "close": 101, "volume": 1, "timestamp": "2"},
    ]
    seed_response = client.post(
        "/market-data/mock/seed",
        json={"symbol": "BTC/KRW", "timeframe": "1h", "candles": candles},
    )
    assert seed_response.status_code == 200

    stored_response = client.get("/market-data/stored?symbol=BTC/KRW&timeframe=1h&limit=10")
    assert stored_response.status_code == 200
    body = stored_response.json()
    assert body["count"] >= 2
    assert body["candles"][-1]["close"] == 101


def test_export_and_reset_endpoints_manage_operator_state():
    client.post(
        "/market-data/mock/seed",
        json={
            "symbol": "BTC/KRW",
            "timeframe": "1h",
            "candles": [
                {"symbol": "BTC/KRW", "timeframe": "1h", "open": 1, "high": 1, "low": 1, "close": 100, "volume": 1, "timestamp": "1"},
            ],
        },
    )
    client.post(
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

    paper_export = client.get("/paper/export")
    assert paper_export.status_code == 200
    assert paper_export.json()["portfolio"]["order_count"] >= 1

    stored_export = client.get("/market-data/stored/export")
    assert stored_export.status_code == 200
    assert stored_export.json()["total_series"] >= 1

    runs_response = client.get("/runs?limit=10")
    assert runs_response.status_code == 200
    assert len(runs_response.json()["runs"]) >= 1

    paper_reset = client.post("/paper/reset")
    assert paper_reset.status_code == 200
    assert paper_reset.json()["portfolio"]["order_count"] == 0

    stored_reset = client.post("/market-data/stored/reset")
    assert stored_reset.status_code == 200
    assert stored_reset.json()["status"] == "cleared"

    runs_reset = client.post("/runs/reset")
    assert runs_reset.status_code == 200
    assert runs_reset.json()["status"] == "cleared"
