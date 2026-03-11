from investment_bot.services.run_history_service import RunHistoryService
from investment_bot.services.run_history_store import RunHistoryStore


def test_run_history_store_records_and_lists_entries(tmp_path):
    service = RunHistoryService(store=RunHistoryStore(str(tmp_path / "run_history.json")))

    first = service.record(kind="dry_run_cycle", payload={"ok": True})
    second = service.record(kind="replay_backtest", payload={"steps": 2})

    assert first["id"] == 1
    assert second["id"] == 2
    recent = service.list_recent(limit=10)
    assert len(recent) == 2
    assert recent[-1]["kind"] == "replay_backtest"
