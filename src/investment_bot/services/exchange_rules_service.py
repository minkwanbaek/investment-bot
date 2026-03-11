from dataclasses import dataclass

from investment_bot.services.upbit_client import UpbitClient


@dataclass
class ExchangeRulesService:
    upbit_client: UpbitClient

    def get_upbit_market_rules(self, symbol: str) -> dict:
        market = self._to_upbit_market(symbol)
        markets = self.upbit_client.get_markets(is_details=True)
        market_info = next((item for item in markets if item.get("market") == market), None)
        if market_info is None:
            raise ValueError(f"unsupported upbit market: {symbol}")

        return {
            "exchange": "upbit",
            "symbol": symbol,
            "market": market,
            "min_order_notional": 5000.0 if market.startswith("KRW-") else 0.0,
            "price_unit_policy": self._price_unit_policy(market),
            "market_info": market_info,
        }

    def normalize_upbit_price(self, symbol: str, price: float) -> dict:
        market = self._to_upbit_market(symbol)
        unit = self._tick_size_for_price(market, price)
        normalized = (price // unit) * unit if unit else price
        return {
            "exchange": "upbit",
            "symbol": symbol,
            "market": market,
            "requested_price": price,
            "tick_size": unit,
            "normalized_price": round(normalized, 8),
        }

    def _to_upbit_market(self, symbol: str) -> str:
        if "/" not in symbol:
            raise ValueError(f"unsupported symbol format: {symbol}")
        base, quote = symbol.split("/", 1)
        return f"{quote}-{base}"

    def _price_unit_policy(self, market: str) -> str:
        if market.startswith("KRW-"):
            return "krw-tiered"
        if market.startswith("BTC-"):
            return "btc-market-default"
        if market.startswith("USDT-"):
            return "usdt-market-default"
        return "unknown"

    def _tick_size_for_price(self, market: str, price: float) -> float:
        if not market.startswith("KRW-"):
            return 0.00000001
        if price >= 2_000_000:
            return 1000
        if price >= 1_000_000:
            return 500
        if price >= 500_000:
            return 100
        if price >= 100_000:
            return 50
        if price >= 10_000:
            return 10
        if price >= 1_000:
            return 1
        if price >= 100:
            return 0.1
        if price >= 10:
            return 0.01
        if price >= 1:
            return 0.001
        if price >= 0.1:
            return 0.0001
        if price >= 0.01:
            return 0.00001
        if price >= 0.001:
            return 0.000001
        if price >= 0.0001:
            return 0.0000001
        return 0.00000001
