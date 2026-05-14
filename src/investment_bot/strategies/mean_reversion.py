from statistics import mean
from investment_bot.models.signal import TradeSignal
from investment_bot.strategies.base import BaseStrategy
from investment_bot.services.paper_broker import PaperBroker


class MeanReversionStrategy(BaseStrategy):
    name = "mean_reversion"
    buy_deviation_threshold = -0.025
    sell_deviation_threshold = 0.035
    managed_rebound_exit_threshold = 0.008
    min_buy_volume_ratio = 1.0

    def generate_signal(self, candles, broker: PaperBroker | None = None):
        closes = [c.close for c in candles]
        volumes = [c.volume for c in candles]
        symbol = candles[-1].symbol if candles else "BTC/KRW"
        if len(closes) < 8:
            return TradeSignal(strategy_name=self.name, symbol=symbol, action="hold", confidence=0.0, reason="insufficient data")
        avg = mean(closes[-8:])
        latest = closes[-1]
        prev = closes[-2]
        position = (broker.positions.get(symbol) if broker else None) or {}
        position_qty = float(position.get("quantity", 0.0) or 0.0)
        average_price = float(position.get("average_price", 0.0) or 0.0)
        rebound_pct = ((latest - average_price) / average_price) if average_price else 0.0
        deviation = (latest - avg) / avg if avg else 0.0
        momentum_pct = ((latest - prev) / prev) if prev else 0.0
        prev_avg_volume = mean(volumes[-8:-1])
        buy_volume_ratio = (volumes[-1] / prev_avg_volume) if prev_avg_volume else 1.0
        volume_confirmed = buy_volume_ratio >= self.min_buy_volume_ratio
        body_confirmed = candles[-1].close >= candles[-1].open
        if deviation <= self.buy_deviation_threshold and momentum_pct >= 0 and volume_confirmed and body_confirmed:
            action = "buy"
        elif deviation >= self.sell_deviation_threshold and momentum_pct <= 0:
            action = "sell"
        else:
            action = "hold"
        confidence = min(max(abs(deviation) * 8, 0.0), 1.0)
        if action == "buy":
            confidence = max(confidence, 0.50)
        meta = {
            "buy_volume_ratio": round(buy_volume_ratio, 6),
            "min_buy_volume_ratio": self.min_buy_volume_ratio,
            "body_confirmed": body_confirmed,
        }
        if position_qty > 0:
            meta = {
                **meta,
                "managed_rebound_exit_threshold": self.managed_rebound_exit_threshold,
                "managed_rebound_exit_reason": "mean_reversion_managed_rebound_exit",
                "rebound_pct": round(rebound_pct, 6),
            }
            return TradeSignal(
                strategy_name=self.name,
                symbol=symbol,
                action="hold",
                confidence=0.0,
                reason="position_open_no_exit",
                meta=meta,
            )
        return TradeSignal(
            strategy_name=self.name,
            symbol=symbol,
            action=action,
            confidence=confidence,
            reason=f"deviation={deviation:.4f}, momentum_pct={momentum_pct:.4f}, buy_volume_ratio={buy_volume_ratio:.4f}, body_confirmed={body_confirmed}",
            meta=meta,
        )
