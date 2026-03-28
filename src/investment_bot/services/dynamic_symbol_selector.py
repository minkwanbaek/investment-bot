from dataclasses import dataclass

from investment_bot.models.market import Candle
from investment_bot.services.market_data_service import MarketDataService


@dataclass
class DynamicSymbolSelector:
    market_data_service: MarketDataService

    def select(self, symbols: list[str], timeframe: str, top_n: int = 10) -> list[str]:
        scored = []
        for symbol in symbols:
            try:
                candles = self.market_data_service.get_recent_candles('live', symbol, timeframe, 30)
            except Exception:
                continue
            if len(candles) < 25:
                continue
            score = self._score(candles)
            scored.append((score, symbol))
        scored.sort(reverse=True)
        return [symbol for _, symbol in scored[:top_n]] or symbols

    def _score(self, candles: list[Candle]) -> float:
        closes = [c.close for c in candles]
        volumes = [c.volume for c in candles]
        latest = closes[-1]
        prev = closes[-2]
        trend = ((latest - closes[0]) / closes[0]) if closes[0] else 0.0
        volatility = ((max(closes[-10:]) - min(closes[-10:])) / latest) if latest else 0.0
        value_series = [c.close * c.volume for c in candles[-10:]]
        volume_series = volumes[-10:]
        traded_value = sum(value_series) / max(len(value_series), 1)
        avg_vol = sum(volume_series[:-1]) / max(len(volume_series[:-1]), 1)
        volume_surge = (volume_series[-1] / avg_vol) if avg_vol else 1.0
        short_momentum = ((latest - prev) / prev) if prev else 0.0
        return round(traded_value * 0.000001 + volatility * 100 + trend * 100 + volume_surge * 10 + short_momentum * 50, 6)
