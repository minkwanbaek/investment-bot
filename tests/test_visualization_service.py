from investment_bot.services.run_history_service import RunHistoryService
from investment_bot.services.run_history_store import RunHistoryStore
from investment_bot.services.visualization_service import VisualizationService


def test_visualization_service_builds_chart_ready_profit_structure(tmp_path):
    history = RunHistoryService(store=RunHistoryStore(str(tmp_path / "run_history.json")))
    history.record(
        kind="semi_live_batch",
        payload={
            "fail_safe": {"stop_reason": "max_alerts_reached"},
            "final_portfolio": {"total_equity": 1010, "total_realized_pnl": 5, "total_unrealized_pnl": 2},
        },
    )
    history.record(
        kind="shadow_cycle",
        payload={
            "portfolio": {"total_equity": 1005, "total_realized_pnl": 3, "total_unrealized_pnl": 1},
        },
    )

    service = VisualizationService(run_history_service=history)
    result = service.summarize_profit_structure(limit=10)

    assert result["run_count"] == 2
    assert len(result["equity_curve"]) == 2
    assert len(result["pnl_waterfall"]) == 2
    assert result["stop_reason_counts"]["max_alerts_reached"] == 1
    assert result["recommended_charts"][0]["type"] == "line"
