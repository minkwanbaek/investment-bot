from statistics import mean
from typing import Sequence

from investment_bot.models.market import Candle


class MarketRegimeClassifier:
    def classify(self, candles: Sequence[Candle]) -> dict:
        closes = [c.close for c in candles]
        if len(closes) < 8:
            return {
                "regime": "unknown",
                "reason": "insufficient_data",
                "volatility_state": "normal",
                "higher_tf_bias": "neutral",
            }

        short_ma = mean(closes[-3:])
        long_ma = mean(closes[-8:])
        latest = closes[-1]
        prev = closes[-2]
        trend_gap_pct = ((short_ma - long_ma) / long_ma) if long_ma else 0.0
        range_pct = ((max(closes[-8:]) - min(closes[-8:])) / min(closes[-8:])) if min(closes[-8:]) else 0.0
        momentum_pct = ((latest - prev) / prev) if prev else 0.0

        atr_approx = mean([abs(c.close - c.open) for c in candles[-14:]]) if len(candles) >= 14 else 0.0
        avg_close = mean(closes[-14:]) if len(closes) >= 14 else mean(closes)
        volatility_ratio = (atr_approx / avg_close) if avg_close else 0.0
        if volatility_ratio < 0.005:
            volatility_state = "low"
        elif volatility_ratio > 0.02:
            volatility_state = "high"
        else:
            volatility_state = "normal"

        if len(closes) >= 24:
            higher_ma_short = mean(closes[-24:-8])
            higher_ma_long = mean(closes[-24:])
            higher_gap = ((higher_ma_short - higher_ma_long) / higher_ma_long) if higher_ma_long else 0.0
            if higher_gap > 0.003:
                higher_tf_bias = "bullish"
            elif higher_gap < -0.003:
                higher_tf_bias = "bearish"
            else:
                higher_tf_bias = "neutral"
        else:
            higher_tf_bias = "neutral"

        if range_pct < 0.01 or abs(trend_gap_pct) < 0.0015:
            regime = "sideways"
        elif trend_gap_pct > 0 and momentum_pct > 0:
            regime = "uptrend"
        elif trend_gap_pct < 0 and momentum_pct < 0:
            regime = "downtrend"
        else:
            regime = "mixed"
        return {
            "regime": regime,
            "trend_gap_pct": round(trend_gap_pct, 6),
            "range_pct": round(range_pct, 6),
            "momentum_pct": round(momentum_pct, 6),
            "volatility_state": volatility_state,
            "higher_tf_bias": higher_tf_bias,
        }
