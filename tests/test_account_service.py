from investment_bot.services.account_service import AccountService


class FakeUpbitClient:
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
    assert result["assets"][0]["total_balance"] == 0.0012
    assert result["assets"][0]["estimated_cost_basis"] == 120000.0


def test_account_service_get_asset_balance_by_symbol():
    service = AccountService(upbit_client=FakeUpbitClient())
    asset = service.get_asset_balance("BTC/KRW")
    assert asset["currency"] == "BTC"
    assert asset["balance"] == 0.001
    assert asset["total_balance"] == 0.0012
