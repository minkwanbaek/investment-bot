from investment_bot.services.run_history_service import RunHistoryService
from investment_bot.services.run_history_store import RunHistoryStore
from investment_bot.services.shadow_service import ShadowService


class FakeSemiLiveService:
    def run_once(self, strategy_name: str, symbol: str, timeframe: str, limit: int = 5):
        return {
            "adapter": "live",
            "strategy": strategy_name,
            "symbol": symbol,
            "timeframe": timeframe,
            "limit": limit,
            "portfolio": {"order_count": 1},
            "broker_result": {"status": "recorded"},
        }


class FakeUpbitClient:
    def get_balances(self):
        return [{"currency": "KRW", "balance": "10000"}]


def test_shadow_service_runs_without_submitting_live_orders(tmp_path):
    service = ShadowService(
        semi_live_service=FakeSemiLiveService(),
        run_history_service=RunHistoryService(store=RunHistoryStore(str(tmp_path / "run_history.json"))),
        upbit_client=FakeUpbitClient(),
    )

    result = service.run_once("trend_following", "BTC/KRW", "1h", 5)
    assert result["mode"] == "shadow"
    assert result["exchange_balance_count"] == 1
    assert result["live_order_submitted"] is False
    assert result["decision"]["broker_result"]["status"] == "recorded"
