from investment_bot.services.exchange_rules_service import ExchangeRulesService
from investment_bot.services.live_execution_service import LiveExecutionService
from investment_bot.services.run_history_service import RunHistoryService
from investment_bot.services.run_history_store import RunHistoryStore


class FakeUpbitClient:
    def get_markets(self, is_details: bool = False):
        return [{"market": "KRW-BTC", "korean_name": "비트코인", "english_name": "Bitcoin"}]


def test_live_execution_preview_normalizes_and_blocks_live_submission(tmp_path):
    service = LiveExecutionService(
        upbit_client=FakeUpbitClient(),
        exchange_rules_service=ExchangeRulesService(upbit_client=FakeUpbitClient()),
        run_history_service=RunHistoryService(store=RunHistoryStore(str(tmp_path / "run_history.json"))),
        live_mode="shadow",
        confirm_live_trading=False,
    )

    preview = service.preview_order(symbol="BTC/KRW", side="buy", price=102913123, volume=0.001)
    blocked = service.submit_order(symbol="BTC/KRW", side="buy", price=102913123, volume=0.001)

    assert preview["normalized_price"] == 102913000
    assert preview["would_submit_live"] is False
    assert blocked["status"] == "blocked"
    assert blocked["reason"] == "live_mode_disabled"
