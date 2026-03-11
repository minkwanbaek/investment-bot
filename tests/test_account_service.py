from investment_bot.services.account_service import AccountService


class FakeUpbitClient:
    def get_balances(self):
        return [
            {"currency": "KRW", "balance": "12345.67", "locked": "0", "avg_buy_price": "0", "unit_currency": "KRW"},
            {"currency": "BTC", "balance": "0.001", "locked": "0.0", "avg_buy_price": "100000000", "unit_currency": "KRW"},
        ]


def test_account_service_summarizes_upbit_balances():
    service = AccountService(upbit_client=FakeUpbitClient())
    result = service.summarize_upbit_balances()
    assert result["exchange"] == "upbit"
    assert result["krw_cash"] == 12345.67
    assert result["asset_count"] == 1
    assert result["assets"][0]["currency"] == "BTC"
    assert result["assets"][0]["estimated_cost_basis"] == 100000.0
