from investment_bot.services.run_history_service import RunHistoryService
from investment_bot.services.run_history_store import RunHistoryStore


def test_run_history_summary_counts_kinds_and_stop_reasons(tmp_path):
    service = RunHistoryService(store=RunHistoryStore(str(tmp_path / "run_history.json")))
    service.record(kind="dry_run_cycle", payload={"portfolio": {"order_count": 1}})
    service.record(
        kind="semi_live_batch",
        payload={
            "fail_safe": {"stop_reason": "max_alerts_reached"},
            "final_portfolio": {"order_count": 2, "total_equity": 1000},
        },
    )

    summary = service.summarize_recent(limit=10)
    assert summary["total_runs"] == 2
    assert summary["kind_counts"]["dry_run_cycle"] == 1
    assert summary["kind_counts"]["semi_live_batch"] == 1
    assert summary["stop_reasons"]["max_alerts_reached"] == 1
    assert summary["latest_portfolio"]["order_count"] == 2
