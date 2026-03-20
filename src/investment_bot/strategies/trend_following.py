from statistics import mean
from investment_bot.models.signal import TradeSignal
from investment_bot.strategies.base import BaseStrategy


class TrendFollowingStrategy(BaseStrategy):
    name = "trend_following"
    min_trend_gap_pct = 0.0015  # 0.15%

    def generate_signal(self, candles):
        closes = [c.close for c in candles]
        symbol = candles[-1].symbol if candles else "BTC/KRW"
        if len(closes) < 8:
            return TradeSignal(strategy_name=self.name, symbol=symbol, action="hold", confidence=0.0, reason="insufficient data")

        short_ma = mean(closes[-3:])
        long_ma = mean(closes[-8:])
        latest = closes[-1]
        prev = closes[-2]
        trend_gap_pct = ((short_ma - long_ma) / long_ma) if long_ma else 0.0
        momentum_pct = ((latest - prev) / prev) if prev else 0.0

        if trend_gap_pct >= self.min_trend_gap_pct and momentum_pct > 0:
            action = "buy"
        elif trend_gap_pct <= -self.min_trend_gap_pct and momentum_pct < 0:
            action = "sell"
        else:
            action = "hold"

        confidence = min(max(abs(trend_gap_pct) * 120, 0.0), 1.0)
        return TradeSignal(
            strategy_name=self.name,
            symbol=symbol,
            action=action,
            confidence=confidence,
            reason=(
                f"short_ma={short_ma:.2f}, long_ma={long_ma:.2f}, "
                f"trend_gap_pct={trend_gap_pct:.4f}, momentum_pct={momentum_pct:.4f}"
            ),
        )
