from investment_bot.services.alert_service import AlertService
from investment_bot.services.fail_safe_service import FailSafeService
from investment_bot.services.run_history_service import RunHistoryService
from investment_bot.services.run_history_store import RunHistoryStore
from investment_bot.services.scheduler_service import SchedulerService


class FakeSemiLiveService:
    def __init__(self):
        self.counter = 0

    def run_once(self, strategy_name: str, symbol: str, timeframe: str, limit: int = 5):
        self.counter += 1
        return {
            "adapter": "live",
            "strategy": strategy_name,
            "symbol": symbol,
            "timeframe": timeframe,
            "limit": limit,
            "portfolio": {
                "order_count": self.counter,
                "starting_cash": 1000,
                "total_equity": 1000,
                "total_unrealized_pnl": 0,
            },
        }


def test_scheduler_service_runs_requested_iterations_and_records_batch(tmp_path):
    history = RunHistoryService(store=RunHistoryStore(str(tmp_path / "run_history.json")))
    service = SchedulerService(
        semi_live_service=FakeSemiLiveService(),
        run_history_service=history,
        fail_safe_service=FailSafeService(alert_service=AlertService(), max_alerts_per_batch=1, max_loss_steps=2),
    )

    result = service.run_semi_live_batch(
        strategy_name="trend_following",
        symbol="BTC/KRW",
        timeframe="1h",
        limit=5,
        iterations=3,
        interval_seconds=0.0,
    )

    assert result["iterations"] == 3
    assert result["completed_iterations"] == 3
    assert len(result["runs"]) == 3
    assert result["final_portfolio"]["order_count"] == 3
    assert result["fail_safe"]["stop"] is False
    recent = history.list_recent(limit=10)
    assert recent[-1]["kind"] == "semi_live_batch"
