from dataclasses import dataclass

from investment_bot.models.market import Candle
from investment_bot.services.market_data_service import MarketDataService


@dataclass
class DynamicSymbolSelector:
    market_data_service: MarketDataService
    min_confirming_volume_surge: float = 1.2
    min_breakout_close_location: float = 0.8

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
            if (
                score > 0
                and self._has_positive_short_momentum(candles)
                and self._has_confirming_volume(candles)
                and self._has_breakout_close_location(candles)
            ):
                scored.append((score, symbol))
        scored.sort(reverse=True)
        return [symbol for _, symbol in scored[:top_n]]

    def _has_breakout_close_location(self, candles: list[Candle]) -> bool:
        latest = candles[-1]
        candle_range = latest.high - latest.low
        if candle_range <= 0:
            return True
        close_location = (latest.close - latest.low) / candle_range
        return close_location >= self.min_breakout_close_location

    def _has_confirming_volume(self, candles: list[Candle]) -> bool:
        if len(candles) < 10:
            return False
        volume_series = [c.volume for c in candles[-10:]]
        avg_vol = sum(volume_series[:-1]) / max(len(volume_series[:-1]), 1)
        return avg_vol > 0 and volume_series[-1] >= avg_vol * self.min_confirming_volume_surge

    def _has_positive_short_momentum(self, candles: list[Candle]) -> bool:
        if len(candles) < 4:
            return False
        recent_base = candles[-4].close
        prev_base = candles[-3].close
        prev = candles[-2].close
        latest = candles[-1].close
        recent_high_close = max(c.close for c in candles[-8:-1])
        return (
            prev_base > 0
            and prev > prev_base
            and latest > prev
            and recent_base > 0
            and latest > recent_base
            and latest > recent_high_close
        )

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
        downside_penalty = max(-trend, 0.0) * 300 + max(-short_momentum, 0.0) * 150
        upside_reward = max(trend, 0.0) * 100 + max(short_momentum, 0.0) * 50
        directional_volume_surge = volume_surge if short_momentum > 0 else 0.0
        liquidity_score = min(traded_value * 0.000001, 20.0)
        return round(liquidity_score + volatility * 100 + directional_volume_surge * 10 + upside_reward - downside_penalty, 6)
