from investment_bot.services.exchange_rules_service import ExchangeRulesService


class FakeUpbitClient:
    def get_markets(self, is_details: bool = False):
        return [
            {"market": "KRW-BTC", "korean_name": "비트코인", "english_name": "Bitcoin"},
        ]


def test_exchange_rules_service_returns_market_rules():
    service = ExchangeRulesService(upbit_client=FakeUpbitClient())
    result = service.get_upbit_market_rules("BTC/KRW")
    assert result["market"] == "KRW-BTC"
    assert result["min_order_notional"] == 5000.0
    assert result["price_unit_policy"] == "krw-tiered"


def test_exchange_rules_service_normalizes_krw_price_by_tick_size():
    service = ExchangeRulesService(upbit_client=FakeUpbitClient())
    result = service.normalize_upbit_price("BTC/KRW", 102913123)
    assert result["tick_size"] == 1000
    assert result["normalized_price"] == 102913000
