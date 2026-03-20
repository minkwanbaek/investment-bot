from statistics import mean
from investment_bot.models.signal import TradeSignal
from investment_bot.strategies.base import BaseStrategy


class MeanReversionStrategy(BaseStrategy):
    name = "mean_reversion"
    buy_deviation_threshold = -0.03
    sell_deviation_threshold = 0.04

    def generate_signal(self, candles):
        closes = [c.close for c in candles]
        symbol = candles[-1].symbol if candles else "BTC/KRW"
        if len(closes) < 8:
            return TradeSignal(strategy_name=self.name, symbol=symbol, action="hold", confidence=0.0, reason="insufficient data")
        avg = mean(closes[-8:])
        latest = closes[-1]
        prev = closes[-2]
        deviation = (latest - avg) / avg if avg else 0.0
        momentum_pct = ((latest - prev) / prev) if prev else 0.0
        if deviation <= self.buy_deviation_threshold and momentum_pct >= 0:
            action = "buy"
        elif deviation >= self.sell_deviation_threshold and momentum_pct <= 0:
            action = "sell"
        else:
            action = "hold"
        confidence = min(max(abs(deviation) * 8, 0.0), 1.0)
        return TradeSignal(
            strategy_name=self.name,
            symbol=symbol,
            action=action,
            confidence=confidence,
            reason=f"deviation={deviation:.4f}, momentum_pct={momentum_pct:.4f}",
        )
