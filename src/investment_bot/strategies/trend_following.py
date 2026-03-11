from statistics import mean
from investment_bot.models.signal import TradeSignal
from investment_bot.strategies.base import BaseStrategy

class TrendFollowingStrategy(BaseStrategy):
    name = "trend_following"

    def generate_signal(self, candles):
        closes = [c.close for c in candles]
        if len(closes) < 5:
            return TradeSignal(strategy_name=self.name, symbol=candles[-1].symbol if candles else "BTC/KRW", action="hold", confidence=0.0, reason="insufficient data")
        short_ma = mean(closes[-3:])
        long_ma = mean(closes[-5:])
        action = "buy" if short_ma > long_ma else "sell" if short_ma < long_ma else "hold"
        confidence = min(abs(short_ma - long_ma) / long_ma if long_ma else 0.0, 1.0)
        return TradeSignal(strategy_name=self.name, symbol=candles[-1].symbol, action=action, confidence=confidence, reason=f"short_ma={short_ma:.2f}, long_ma={long_ma:.2f}")
