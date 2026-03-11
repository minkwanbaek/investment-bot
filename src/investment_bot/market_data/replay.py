from investment_bot.market_data.base import MarketDataAdapter
from investment_bot.models.market import Candle


class ReplayMarketDataAdapter(MarketDataAdapter):
    name = "replay"

    def __init__(self):
        self._cursor: dict[tuple[str, str], int] = {}
        self._series: dict[tuple[str, str], list[Candle]] = {}

    def load(self, symbol: str, timeframe: str, candles: list[Candle]) -> None:
        key = (symbol, timeframe)
        self._series[key] = candles
        self._cursor[key] = min(len(candles), 1)

    def advance(self, symbol: str, timeframe: str, steps: int = 1) -> int:
        key = (symbol, timeframe)
        if key not in self._series:
            raise ValueError(f"no replay candles loaded for {symbol} {timeframe}")
        self._cursor[key] = min(len(self._series[key]), self._cursor.get(key, 1) + steps)
        return self._cursor[key]

    def get_recent_candles(self, symbol: str, timeframe: str, limit: int) -> list[Candle]:
        key = (symbol, timeframe)
        candles = self._series.get(key, [])
        if not candles:
            raise ValueError(f"no replay candles loaded for {symbol} {timeframe}")
        cursor = self._cursor.get(key, min(len(candles), limit))
        start = max(0, cursor - limit)
        return candles[start:cursor]
