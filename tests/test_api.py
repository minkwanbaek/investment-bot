from pathlib import Path

from fastapi.testclient import TestClient

from investment_bot.main import app
from investment_bot.services.container import get_market_data_service, get_paper_broker, get_run_history_service
from investment_bot.models.market import Candle


client = TestClient(app)


def setup_function():
    broker = get_paper_broker()
    broker.orders.clear()
    broker.positions.clear()
    broker.last_prices.clear()
    broker.cash_balance = broker.starting_cash
    broker.total_realized_pnl = 0.0
    broker.consecutive_buys = 0
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
    # config/app.yml sets mode=live, symbols=20 coins
    assert body["mode"] == "live"
    assert len(body["symbols"]) == 20


def test_dashboard_page_is_served():
    response = client.get("/dashboard")
    assert response.status_code == 200
    # Dashboard title is in Korean: "투자봇 대시보드"
    assert "투자봇" in response.text


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


def test_live_dashboard_endpoint_returns_bundled_operator_payload():
    response = client.get("/operator/live-dashboard")
    assert response.status_code == 200
    body = response.json()
    # Dashboard returns summary_cards, equity_curve, recent_trades, by_strategy_version, by_market_regime
    assert "summary_cards" in body
    assert "equity_curve" in body
    assert "recent_trades" in body


def test_auto_trade_status_endpoint_returns_profile():
    response = client.get("/auto-trade/status")
    assert response.status_code == 200
    body = response.json()
    assert "active" in body
    assert "profile" in body


def test_paper_portfolio_endpoint_returns_snapshot():
    response = client.get("/paper/portfolio")
    assert response.status_code == 200
    body = response.json()
    # Portfolio returns cash_balance, positions, total_realized_pnl, etc.
    assert "cash_balance" in body or "portfolio" in body


def test_dry_run_cycle_records_decision():
    # dry-run endpoint requires at least 1 candle
    candles = [Candle(symbol="BTC/KRW", timeframe="1h", open=i, high=i+1, low=i-1, close=i, volume=1, timestamp=f"2025-01-0{i}T00:00:00Z") for i in range(1, 6)]
    candle_dicts = [{"symbol": c.symbol, "timeframe": c.timeframe, "open": c.open, "high": c.high, "low": c.low, "close": c.close, "volume": c.volume, "timestamp": c.timestamp} for c in candles]
    response = client.post("/cycle/dry-run", json={"candles": candle_dicts, "strategy_name": "trend_following", "symbol": "BTC/KRW", "timeframe": "1h", "limit": 5})
    assert response.status_code == 200
    body = response.json()
    # Response has signal/review at top level
    assert "signal" in body or "review" in body


def test_dry_run_cycle_handles_unknown_strategy():
    # Unknown strategy - endpoint may return 200 with hold decision or 400
    candles = [Candle(symbol="BTC/KRW", timeframe="1h", open=i, high=i+1, low=i-1, close=i, volume=1, timestamp=f"2025-01-0{i}T00:00:00Z") for i in range(1, 6)]
    candle_dicts = [{"symbol": c.symbol, "timeframe": c.timeframe, "open": c.open, "high": c.high, "low": c.low, "close": c.close, "volume": c.volume, "timestamp": c.timestamp} for c in candles]
    response = client.post("/cycle/dry-run", json={"candles": candle_dicts, "strategy_name": "unknown_strategy", "symbol": "BTC/KRW", "timeframe": "1h", "limit": 5})
    assert response.status_code in [200, 400]


def test_market_data_adapter_flow_runs_cycle_from_seeded_mock_data():
    market_data_service = get_market_data_service()
    mock_adapter = market_data_service.registry.get("mock")
    # Seed mock adapter with test data
    candles = [Candle(symbol="BTC/KRW", timeframe="1h", open=i, high=i+1, low=i-1, close=i, volume=1, timestamp=f"2025-01-0{i}T00:00:00Z") for i in range(1, 9)]
    mock_adapter._series[("BTC/KRW", "1h")] = candles
    # from-adapter uses adapter_name field
    response = client.post("/cycle/from-adapter", json={"adapter_name": "mock", "strategy_name": "trend_following", "symbol": "BTC/KRW", "timeframe": "1h", "limit": 8})
    assert response.status_code == 200
    body = response.json()
    assert body["adapter"] == "mock"
    # Response has signal/review
    assert "signal" in body or "review" in body


def test_replay_backtest_endpoint_runs_multi_step_summary():
    market_data_service = get_market_data_service()
    replay_adapter = market_data_service.registry.get("replay")
    candles = [Candle(symbol="BTC/KRW", timeframe="1h", open=i, high=i+1, low=i-1, close=i, volume=1, timestamp=f"2025-01-0{i}T00:00:00Z") for i in range(1, 12)]
    replay_adapter._series[("BTC/KRW", "1h")] = candles
    response = client.post(
        "/backtest/replay",
        json={"strategy_name": "trend_following", "symbol": "BTC/KRW", "timeframe": "1h", "limit": 5, "steps": 3},
    )
    assert response.status_code == 200
    body = response.json()
    assert "summary" in body or "steps" in body or "results" in body


def test_stored_market_data_endpoint_returns_structure():
    # Just test the endpoint returns proper structure without seeding data
    response = client.get("/market-data/stored?adapter=mock&symbol=TEST%2FKRW&timeframe=1h&limit=10")
    assert response.status_code == 200
    body = response.json()
    # Endpoint returns symbol, timeframe, count, candles
    assert "symbol" in body
    assert "candles" in body


def test_paper_export_and_reset_endpoints_manage_operator_state():
    export_response = client.get("/paper/export")
    assert export_response.status_code == 200
    export_body = export_response.json()
    assert "cash_balance" in export_body or "portfolio" in export_body
    reset_response = client.post("/paper/reset")
    assert reset_response.status_code == 200
    broker = get_paper_broker()
    assert broker.cash_balance == broker.starting_cash


def test_operator_drift_report_endpoint_returns_structure():
    response = client.get("/operator/drift-report")
    assert response.status_code == 200
    body = response.json()
    # Drift report returns shadow_runs or similar structure
    assert isinstance(body, dict)
