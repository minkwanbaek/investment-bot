from investment_bot.market_data.base import MarketDataAdapter
from investment_bot.models.market import Candle


class MockMarketDataAdapter(MarketDataAdapter):
    name = "mock"

    def __init__(self):
        self._series: dict[tuple[str, str], list[Candle]] = {}

    def seed(self, symbol: str, timeframe: str, candles: list[Candle]) -> None:
        self._series[(symbol, timeframe)] = candles

    def get_recent_candles(self, symbol: str, timeframe: str, limit: int) -> list[Candle]:
        candles = self._series.get((symbol, timeframe), [])
        if not candles:
            raise ValueError(f"no seeded candles for {symbol} {timeframe}")
        return candles[-limit:]
