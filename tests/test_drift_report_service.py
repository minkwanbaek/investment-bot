from investment_bot.services.drift_report_service import DriftReportService
from investment_bot.services.paper_broker import PaperBroker
from investment_bot.services.run_history_service import RunHistoryService
from investment_bot.services.run_history_store import RunHistoryStore


def test_drift_report_returns_no_shadow_data_when_no_shadow_run_exists(tmp_path):
    history = RunHistoryService(store=RunHistoryStore(str(tmp_path / "run_history.json")))
    broker = PaperBroker(starting_cash=1000, ledger_store=None, trading_fee_pct=0.0, slippage_pct=0.0, min_order_notional=0.0)

    result = DriftReportService(run_history_service=history, paper_broker=broker).summarize(limit=10)

    assert result["status"] == "no_shadow_data"
    assert result["shadow_reference"] is None
    assert result["position_drifts"] == []


def test_drift_report_compares_latest_shadow_run_against_paper_state(tmp_path):
    history = RunHistoryService(store=RunHistoryStore(str(tmp_path / "run_history.json")))
    broker = PaperBroker(starting_cash=100000, ledger_store=None, trading_fee_pct=0.0, slippage_pct=0.0, min_order_notional=0.0)
    broker.submit(
        {
            "strategy_name": "trend_following",
            "symbol": "BTC/KRW",
            "action": "buy",
            "confidence": 1.0,
            "size_scale": 1.0,
            "reason": "buy",
        },
        execution_price=10000,
    )

    history.record(
        kind="shadow_cycle",
        payload={
            "exchange_account_summary": {
                "exchange": "upbit",
                "asset_count": 1,
                "krw_cash": 85000.0,
                "assets": [
                    {
                        "currency": "BTC",
                        "balance": 0.8,
                        "locked": 0.0,
                        "avg_buy_price": 9000.0,
                        "unit_currency": "KRW",
                        "estimated_cost_basis": 7200.0,
                    }
                ],
            }
        },
    )

    result = DriftReportService(run_history_service=history, paper_broker=broker).summarize(limit=10)

    assert result["status"] == "ok"
    assert result["shadow_reference"]["exchange_account_summary"]["asset_count"] == 1
    assert result["cash_drift"]["difference"] == 5000.0
    btc = next(item for item in result["position_drifts"] if item["asset"] == "BTC")
    assert btc["paper_quantity"] == 1.0
    assert btc["shadow_quantity"] == 0.8
    assert btc["quantity_difference"] == 0.2
    assert result["recommendations"]
