from statistics import mean
from investment_bot.models.signal import TradeSignal
from investment_bot.strategies.base import BaseStrategy

class MeanReversionStrategy(BaseStrategy):
    name = "mean_reversion"

    def generate_signal(self, candles):
        closes = [c.close for c in candles]
        if len(closes) < 5:
            return TradeSignal(strategy_name=self.name, symbol=candles[-1].symbol if candles else "BTC/KRW", action="hold", confidence=0.0, reason="insufficient data")
        avg = mean(closes[-5:])
        latest = closes[-1]
        deviation = (latest - avg) / avg if avg else 0.0
        if deviation <= -0.02:
            action = "buy"
        elif deviation >= 0.02:
            action = "sell"
        else:
            action = "hold"
        return TradeSignal(strategy_name=self.name, symbol=candles[-1].symbol, action=action, confidence=min(abs(deviation) * 10, 1.0), reason=f"deviation={deviation:.4f}")
