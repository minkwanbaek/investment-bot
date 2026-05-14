from investment_bot.services.account_service import AccountService


class FakeUpbitClient:
    def get_markets(self):
        return [{"market": "KRW-BTC"}]

    def get_ticker(self, markets):
        payload = []
        if "KRW-BTC" in markets:
            payload.append({"market": "KRW-BTC", "trade_price": 110000000})
        return payload

    def get_balances(self):
        return [
            {"currency": "KRW", "balance": "12345.67", "locked": "0", "avg_buy_price": "0", "unit_currency": "KRW"},
            {"currency": "BTC", "balance": "0.001", "locked": "0.0002", "avg_buy_price": "100000000", "unit_currency": "KRW"},
        ]


def test_account_service_summarizes_upbit_balances():
    service = AccountService(upbit_client=FakeUpbitClient())
    result = service.summarize_upbit_balances()
    assert result["exchange"] == "upbit"
    assert result["krw_cash"] == 12345.67
    assert result["asset_count"] == 1
    assert result["assets"][0]["currency"] == "BTC"
    assert result["assets"][0]["balance"] == 0.001
    assert result["assets"][0]["market_value"] == 132000.0
    assert result["assets"][0]["liquidation_value"] is not None
    assert result["assets"][0]["sellable_now"] is True
    assert result["assets"][0]["sell_block_reason"] is None


def test_account_service_internal_snapshot_preserves_trading_fields():
    service = AccountService(upbit_client=FakeUpbitClient())
    result = service.summarize_upbit_balances_internal()
    assert result["assets"][0]["total_balance"] == 0.0012
    assert result["assets"][0]["estimated_cost_basis"] == 120000.0
    assert result["assets"][0]["current_price"] == 110000000.0
    assert result["assets"][0]["estimated_market_value"] == 132000.0


def test_account_service_get_asset_balance_by_symbol():
    service = AccountService(upbit_client=FakeUpbitClient())
    asset = service.get_asset_balance("BTC/KRW")
    assert asset["currency"] == "BTC"
    assert asset["balance"] == 0.001
    assert asset["total_balance"] == 0.0012


class FakeUpbitClientWithDelistedAsset(FakeUpbitClient):
    def get_markets(self):
        return [{"market": "KRW-BTC"}]

    def get_balances(self):
        return super().get_balances() + [
            {"currency": "BTG", "balance": "1", "locked": "0", "avg_buy_price": "1000", "unit_currency": "KRW"},
        ]


def test_account_service_ignores_delisted_market_in_batch_ticker_lookup():
    service = AccountService(upbit_client=FakeUpbitClientWithDelistedAsset())
    result = service.summarize_upbit_balances()
    assets = {item["currency"]: item for item in result["assets"]}
    assert assets["BTC"]["market_value"] == 132000.0
    assert assets["BTG"]["market_value"] is None
    assert assets["BTG"]["liquidation_value"] is None
    assert assets["BTG"]["sellable_now"] is False
    assert assets["BTG"]["sell_block_reason"] == "inactive_market"


class FakeUpbitClientWithMissingTicker(FakeUpbitClient):
    def get_markets(self):
        return [{"market": "KRW-BTC"}, {"market": "KRW-BTG"}]

    def get_ticker(self, markets):
        return [{"market": "KRW-BTC", "trade_price": 110000000}]

    def get_balances(self):
        return super().get_balances() + [
            {"currency": "BTG", "balance": "1", "locked": "0", "avg_buy_price": "1000", "unit_currency": "KRW"},
        ]


def test_account_service_marks_missing_ticker_without_zero_fallback():
    service = AccountService(upbit_client=FakeUpbitClientWithMissingTicker())
    result = service.summarize_upbit_balances()
    assets = {item["currency"]: item for item in result["assets"]}
    assert assets["BTG"]["market_value"] is None
    assert assets["BTG"]["liquidation_value"] is None
    assert assets["BTG"]["sellable_now"] is False
    assert assets["BTG"]["sell_block_reason"] == "no_ticker"
