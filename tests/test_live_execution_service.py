from investment_bot.services.account_service import AccountService
from investment_bot.core.settings import get_settings
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

    def create_order(self, market: str, side: str, ord_type: str, volume: str | None = None, price: str | None = None):
        return {"uuid": "test-order", "market": market, "side": side, "volume": volume, "price": price, "ord_type": ord_type}


class ExactMinCashUpbitClient(FakeUpbitClient):
    def get_balances(self):
        return [
            {"currency": "KRW", "balance": "5000", "locked": "0", "avg_buy_price": "0", "unit_currency": "KRW"},
        ]


class BoundarySellBalanceUpbitClient(FakeUpbitClient):
    def get_balances(self):
        return [
            {"currency": "KRW", "balance": "0", "locked": "0", "avg_buy_price": "0", "unit_currency": "KRW"},
            {"currency": "BTC", "balance": "0.000048589999", "locked": "0", "avg_buy_price": "100000000", "unit_currency": "KRW"},
        ]


class SlippageBoundarySellUpbitClient(FakeUpbitClient):
    def get_balances(self):
        return [
            {"currency": "KRW", "balance": "0", "locked": "0", "avg_buy_price": "0", "unit_currency": "KRW"},
            {"currency": "BTC", "balance": "5.001", "locked": "0", "avg_buy_price": "1000", "unit_currency": "KRW"},
        ]


class ExactMinCashUpbitClient(FakeUpbitClient):
    def get_balances(self):
        return [
            {"currency": "KRW", "balance": "5000", "locked": "0", "avg_buy_price": "0", "unit_currency": "KRW"},
        ]


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
    assert submitted["submitted_payload"]["ord_type"] == "price"
    assert submitted["submitted_payload"]["price"] == "102913"
    assert "volume" not in submitted["submitted_payload"]


def test_live_execution_floors_krw_market_buy_requested_quote_amount_to_whole_krw(tmp_path):
    client = FakeUpbitClient()
    service = LiveExecutionService(
        upbit_client=client,
        exchange_rules_service=ExchangeRulesService(upbit_client=client),
        run_history_service=RunHistoryService(store=RunHistoryStore(str(tmp_path / "run_history.json"))),
        account_service=AccountService(upbit_client=client),
        live_mode="live",
        confirm_live_trading=True,
    )

    submitted = service.submit_order(symbol="BTC/KRW", side="buy", price=1000.1, volume=5.0005)

    assert submitted["status"] == "submitted"
    assert submitted["notional"] == 5001.00005
    assert submitted["submitted_payload"]["ord_type"] == "price"
    assert submitted["submitted_payload"]["price"] == "5001"
    assert "." not in submitted["submitted_payload"]["price"]
    assert "volume" not in submitted["submitted_payload"]


def test_live_execution_market_buy_preserves_requested_quote_notional_after_tick_normalization(tmp_path):
    client = FakeUpbitClient()
    service = LiveExecutionService(
        upbit_client=client,
        exchange_rules_service=ExchangeRulesService(upbit_client=client),
        run_history_service=RunHistoryService(store=RunHistoryStore(str(tmp_path / "run_history.json"))),
        account_service=AccountService(upbit_client=client),
        live_mode="live",
        confirm_live_trading=True,
    )

    raw_price = 102_913_123
    volume_for_10000_krw = 10_000 / raw_price
    normalized_price = 102_913_000
    old_tick_normalized_notional = normalized_price * volume_for_10000_krw

    submitted = service.submit_order(symbol="BTC/KRW", side="buy", price=raw_price, volume=volume_for_10000_krw)

    assert old_tick_normalized_notional < 10_000
    assert submitted["status"] == "submitted"
    assert submitted["notional"] == 10_000
    assert submitted["submitted_payload"]["ord_type"] == "price"
    assert submitted["submitted_payload"]["price"] == "10000"
    assert "volume" not in submitted["submitted_payload"]


def test_live_execution_market_buy_reports_slippage_adjusted_received_volume(tmp_path):
    client = FakeUpbitClient()
    service = LiveExecutionService(
        upbit_client=client,
        exchange_rules_service=ExchangeRulesService(upbit_client=client),
        run_history_service=RunHistoryService(store=RunHistoryStore(str(tmp_path / "run_history.json"))),
        account_service=AccountService(upbit_client=client),
        live_mode="paper",
        confirm_live_trading=False,
    )

    raw_price = 102_913_123
    requested_quote = 10_000
    raw_volume = requested_quote / raw_price
    normalized_price = 102_913_000
    expected_fill_price = normalized_price * (1 + (get_settings().slippage_pct / 100))

    submitted = service.submit_order(symbol="BTC/KRW", side="buy", price=raw_price, volume=raw_volume)

    assert submitted["status"] == "submitted"
    assert submitted["notional"] == requested_quote
    assert submitted["volume"] == requested_quote / expected_fill_price
    assert submitted["volume"] < requested_quote / normalized_price
    assert submitted["submitted_payload"]["price"] == "10000"
    assert "volume" not in submitted["submitted_payload"]


def test_live_execution_paper_mode_records_dry_run_submission_without_api_order(tmp_path):
    client = FakeUpbitClient()
    service = LiveExecutionService(
        upbit_client=client,
        exchange_rules_service=ExchangeRulesService(upbit_client=client),
        run_history_service=RunHistoryService(store=RunHistoryStore(str(tmp_path / "run_history.json"))),
        account_service=AccountService(upbit_client=client),
        live_mode="paper",
        confirm_live_trading=False,
    )

    submitted = service.submit_order(symbol="BTC/KRW", side="buy", price=102913123, volume=0.001)

    assert submitted["status"] == "submitted"
    assert submitted["dry_run_only"] is True
    assert submitted["order"]["dry_run_only"] is True
    assert submitted["submitted_payload"]["market"] == "KRW-BTC"
    assert submitted["submitted_payload"]["side"] == "bid"
    assert submitted["submitted_payload"]["ord_type"] == "price"
    assert submitted["submitted_payload"]["price"] == "102913"
    assert "volume" not in submitted["submitted_payload"]
    assert submitted["submitted_payload"]["dry_run_only"] is True
    assert submitted["order"]["uuid"] is None


def test_live_execution_submit_reuses_approved_preview(tmp_path):
    client = FakeUpbitClient()
    run_history_service = RunHistoryService(store=RunHistoryStore(str(tmp_path / "run_history.json")))
    service = LiveExecutionService(
        upbit_client=client,
        exchange_rules_service=ExchangeRulesService(upbit_client=client),
        run_history_service=run_history_service,
        account_service=AccountService(upbit_client=client),
        live_mode="paper",
        confirm_live_trading=False,
    )

    preview = service.preview_order(symbol="BTC/KRW", side="buy", price=102913123, volume=0.001)
    submitted = service.submit_order(symbol="BTC/KRW", side="buy", price=102913123, volume=0.001, preview=preview)

    assert submitted["status"] == "submitted"
    assert submitted["submitted_payload"]["price"] == "102913"
    preview_rows = [row for row in run_history_service.list_recent(limit=10) if row["kind"] == "live_order_preview"]
    assert len(preview_rows) == 1


def test_live_execution_preview_blocks_buy_when_fee_pushes_min_order_over_cash(tmp_path):
    client = ExactMinCashUpbitClient()
    service = LiveExecutionService(
        upbit_client=client,
        exchange_rules_service=ExchangeRulesService(upbit_client=client),
        run_history_service=RunHistoryService(store=RunHistoryStore(str(tmp_path / "run_history.json"))),
        account_service=AccountService(upbit_client=client),
        live_mode="live",
        confirm_live_trading=True,
    )

    preview = service.preview_order(symbol="BTC/KRW", side="buy", price=1000, volume=5)

    assert preview["allowed"] is False
    assert preview["reason"] == "below_min_order_notional"
    assert preview["notional"] < preview["min_order_notional"]
    assert preview["total_cost"] <= 5000


def test_live_execution_submit_preserves_specific_preview_block_reason(tmp_path):
    client = ExactMinCashUpbitClient()
    service = LiveExecutionService(
        upbit_client=client,
        exchange_rules_service=ExchangeRulesService(upbit_client=client),
        run_history_service=RunHistoryService(store=RunHistoryStore(str(tmp_path / "run_history.json"))),
        account_service=AccountService(upbit_client=client),
        live_mode="live",
        confirm_live_trading=True,
    )

    submitted = service.submit_order(symbol="BTC/KRW", side="buy", price=1000, volume=5)

    assert submitted["status"] == "blocked"
    assert submitted["reason"] == "below_min_order_notional"
    assert submitted["notional"] < submitted["min_order_notional"]


def test_live_execution_preview_blocks_buy_when_fee_pushes_min_order_over_cash(tmp_path):
    client = ExactMinCashUpbitClient()
    service = LiveExecutionService(
        upbit_client=client,
        exchange_rules_service=ExchangeRulesService(upbit_client=client),
        run_history_service=RunHistoryService(store=RunHistoryStore(str(tmp_path / "run_history.json"))),
        account_service=AccountService(upbit_client=client),
        live_mode="live",
        confirm_live_trading=True,
    )

    preview = service.preview_order(symbol="BTC/KRW", side="buy", price=1000, volume=5)

    assert preview["allowed"] is False
    assert preview["notional"] < preview["min_order_notional"]
    assert preview["total_cost"] <= 5000


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

    preview = service.preview_order(symbol="BTC/KRW", side="sell", price=1000, volume=10)
    assert preview["allowed"] is False
    assert preview["asset_summary"]["balance"] == 0.002


def test_live_execution_trims_sell_to_free_balance_when_still_min_executable(tmp_path):
    client = FakeUpbitClient()
    run_history_service = RunHistoryService(store=RunHistoryStore(str(tmp_path / "run_history.json")))
    service = LiveExecutionService(
        upbit_client=client,
        exchange_rules_service=ExchangeRulesService(upbit_client=client),
        run_history_service=run_history_service,
        account_service=AccountService(upbit_client=client),
        live_mode="live",
        confirm_live_trading=True,
    )

    submitted = service.submit_order(symbol="BTC/KRW", side="sell", price=102913123, volume=0.01)

    assert submitted["status"] == "submitted"
    assert submitted["volume"] == 0.002
    assert submitted["submitted_payload"]["volume"] == "0.002"
    assert submitted["submitted_payload"]["ord_type"] == "market"
    assert "price" not in submitted["submitted_payload"]
    assert submitted["notional"] >= submitted["min_order_notional"]
    submit_rows = [row for row in run_history_service.list_recent(limit=10) if row["kind"] == "live_order_submit"]
    assert submit_rows[-1]["payload"]["volume"] == 0.002


def test_live_execution_blocks_boundary_sell_after_payload_volume_floor(tmp_path):
    client = BoundarySellBalanceUpbitClient()
    service = LiveExecutionService(
        upbit_client=client,
        exchange_rules_service=ExchangeRulesService(upbit_client=client),
        run_history_service=RunHistoryService(store=RunHistoryStore(str(tmp_path / "run_history.json"))),
        account_service=AccountService(upbit_client=client),
        live_mode="live",
        confirm_live_trading=True,
    )

    submitted = service.submit_order(symbol="BTC/KRW", side="sell", price=102913123, volume=0.01)

    assert submitted["status"] == "blocked"
    assert submitted["reason"] == "insufficient_asset_balance_for_min_order"
    assert submitted["volume"] == 0.00004858
    assert submitted["notional"] < submitted["min_order_notional"]


def test_live_execution_blocks_sell_when_slippage_puts_notional_below_min_order(tmp_path):
    client = SlippageBoundarySellUpbitClient()
    service = LiveExecutionService(
        upbit_client=client,
        exchange_rules_service=ExchangeRulesService(upbit_client=client),
        run_history_service=RunHistoryService(store=RunHistoryStore(str(tmp_path / "run_history.json"))),
        account_service=AccountService(upbit_client=client),
        live_mode="live",
        confirm_live_trading=True,
    )

    submitted = service.submit_order(symbol="BTC/KRW", side="sell", price=1000, volume=5.001)

    assert submitted["status"] == "blocked"
    assert submitted["reason"] == "below_min_order_notional"
    assert submitted["notional"] == 4998.4995
    assert submitted["volume"] == 5.001
    assert submitted["notional"] < submitted["min_order_notional"]
