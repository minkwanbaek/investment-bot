from investment_bot.services.account_service import AccountService
from investment_bot.services.exchange_rules_service import ExchangeRulesService
from investment_bot.services.live_execution_service import LiveExecutionService
from investment_bot.services.run_history_service import RunHistoryService
from investment_bot.services.run_history_store import RunHistoryStore


class FakeUpbitClient:
    def get_markets(self, is_details: bool = False):
        return [{"market": "KRW-BTC", "korean_name": "비트코인", "english_name": "Bitcoin"}]

    def get_balances(self):
        return [
            {"currency": "KRW", "balance": "1000000", "locked": "0", "avg_buy_price": "0", "unit_currency": "KRW"},
            {"currency": "BTC", "balance": "0.002", "locked": "0", "avg_buy_price": "100000000", "unit_currency": "KRW"},
        ]

    def create_limit_order(self, market: str, side: str, volume: str, price: str, ord_type: str = "limit"):
        return {"uuid": "test-order", "market": market, "side": side, "volume": volume, "price": price, "ord_type": ord_type}


def test_live_execution_preview_normalizes_and_blocks_live_submission(tmp_path):
    client = FakeUpbitClient()
    service = LiveExecutionService(
        upbit_client=client,
        exchange_rules_service=ExchangeRulesService(upbit_client=client),
        run_history_service=RunHistoryService(store=RunHistoryStore(str(tmp_path / "run_history.json"))),
        account_service=AccountService(upbit_client=client),
        live_mode="shadow",
        confirm_live_trading=False,
    )

    preview = service.preview_order(symbol="BTC/KRW", side="buy", price=102913123, volume=0.001)
    blocked = service.submit_order(symbol="BTC/KRW", side="buy", price=102913123, volume=0.001)

    assert preview["normalized_price"] == 102913000
    assert preview["would_submit_live"] is False
    assert blocked["status"] == "blocked"
    assert blocked["reason"] == "live_mode_disabled"


def test_live_execution_submits_when_live_mode_and_confirmation_are_enabled(tmp_path):
    client = FakeUpbitClient()
    service = LiveExecutionService(
        upbit_client=client,
        exchange_rules_service=ExchangeRulesService(upbit_client=client),
        run_history_service=RunHistoryService(store=RunHistoryStore(str(tmp_path / "run_history.json"))),
        account_service=AccountService(upbit_client=client),
        live_mode="live",
        confirm_live_trading=True,
    )

    submitted = service.submit_order(symbol="BTC/KRW", side="buy", price=102913123, volume=0.001)
    assert submitted["status"] == "submitted"
    assert submitted["order"]["uuid"] == "test-order"
    assert submitted["submitted_payload"]["market"] == "KRW-BTC"
    assert submitted["submitted_payload"]["side"] == "bid"
    assert submitted["submitted_payload"]["ord_type"] == "limit"


def test_live_execution_blocks_sell_when_balance_is_insufficient(tmp_path):
    client = FakeUpbitClient()
    service = LiveExecutionService(
        upbit_client=client,
        exchange_rules_service=ExchangeRulesService(upbit_client=client),
        run_history_service=RunHistoryService(store=RunHistoryStore(str(tmp_path / "run_history.json"))),
        account_service=AccountService(upbit_client=client),
        live_mode="live",
        confirm_live_trading=True,
    )

    preview = service.preview_order(symbol="BTC/KRW", side="sell", price=102913123, volume=0.01)
    assert preview["allowed"] is False
    assert preview["asset_summary"]["balance"] == 0.002
