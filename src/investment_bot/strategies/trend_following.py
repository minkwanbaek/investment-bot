from statistics import mean
from investment_bot.models.signal import TradeSignal
from investment_bot.strategies.base import BaseStrategy


class TrendFollowingStrategy(BaseStrategy):
    name = "trend_following"
    min_trend_gap_pct = 0.0010  # 0.10%
    min_entry_momentum_pct = 0.00035  # 0.035%
    # Keep the default volume gate aligned with DynamicSymbolSelector.min_confirming_volume_surge
    # so the selector does not reject setups that the strategy would immediately buy.
    min_entry_volume_ratio = 1.31
    min_entry_close_location = 0.75
    max_entry_momentum_pct = 0.028
    strong_entry_close_location = 0.84
    strong_entry_volume_ratio = 1.60
    strong_entry_momentum_pct = 0.0012
    require_recent_high_breakout = True
    require_entry_green_body = True
    
    # 청산 조건
    stop_loss_pct = -0.015  # -1.5%
    take_profit_pct = 0.05  # +5%

    def generate_signal(self, candles, broker=None):
        closes = [c.close for c in candles]
        volumes = [c.volume for c in candles]
        symbol = candles[-1].symbol if candles else "BTC/KRW"
        if len(closes) < 8:
            return TradeSignal(strategy_name=self.name, symbol=symbol, action="hold", confidence=0.0, reason="insufficient data")

        short_ma = mean(closes[-3:])
        long_ma = mean(closes[-8:])
        latest = closes[-1]
        prev = closes[-2]
        latest_candle = candles[-1]
        trend_gap_pct = ((short_ma - long_ma) / long_ma) if long_ma else 0.0
        momentum_pct = ((latest - prev) / prev) if prev else 0.0
        prev_avg_volume = mean(volumes[-8:-1])
        entry_volume_ratio = (volumes[-1] / prev_avg_volume) if prev_avg_volume else 1.0
        latest_range = latest_candle.high - latest_candle.low
        entry_close_location = ((latest_candle.close - latest_candle.low) / latest_range) if latest_range > 0 else 1.0
        entry_green_body_confirmed = latest_candle.close >= latest_candle.open
        recent_high_close = max(closes[-8:-1])
        
        # Near-miss observability: structured metrics
        buy_threshold_pct = self.min_trend_gap_pct
        trend_gap_to_threshold_pct = trend_gap_pct / buy_threshold_pct if buy_threshold_pct > 0 else 0.0

        # 포지션 보유 중이면 전략은 entry 대신 exit 힌트만 제공하고,
        # 실제 청산 판단/우선순위는 trading_cycle -> exit slice가 담당한다.
        position_open = False
        if broker is not None:
            position = broker.positions.get(symbol, {})
            quantity = position.get("quantity", 0.0)
            if quantity > 0:
                position_open = True

        # 진입 신호 로직
        volume_confirmed = entry_volume_ratio >= self.min_entry_volume_ratio
        strong_impulse_close_confirmed = (
            entry_close_location >= self.strong_entry_close_location
            and entry_volume_ratio >= self.strong_entry_volume_ratio
            and momentum_pct >= self.strong_entry_momentum_pct
        )
        close_confirmed = entry_close_location >= self.min_entry_close_location or strong_impulse_close_confirmed
        body_confirmed = entry_green_body_confirmed if self.require_entry_green_body else True
        breakout_confirmed = (latest > recent_high_close) if self.require_recent_high_breakout else True
        if trend_gap_pct >= self.min_trend_gap_pct and momentum_pct >= self.min_entry_momentum_pct and volume_confirmed and close_confirmed and body_confirmed and breakout_confirmed:
            if momentum_pct <= self.max_entry_momentum_pct:
                action = "buy"
            else:
                action = "hold"
        elif trend_gap_pct <= -self.min_trend_gap_pct and momentum_pct <= -self.min_entry_momentum_pct:
            action = "sell"
        else:
            action = "hold"

        confidence = min(max(abs(trend_gap_pct) * 120, 0.0), 1.0)
        
        # Near-miss observability: structured meta
        meta = {
            "short_ma": round(short_ma, 6),
            "long_ma": round(long_ma, 6),
            "trend_reversal_hint": short_ma < long_ma,
            "strategy_stop_loss_pct": self.stop_loss_pct,
            "strategy_take_profit_pct": self.take_profit_pct,
            "trend_gap_pct": round(trend_gap_pct, 6),
            "momentum_pct": round(momentum_pct, 6),
            "entry_volume_ratio": round(entry_volume_ratio, 6),
            "min_entry_volume_ratio": self.min_entry_volume_ratio,
            "entry_close_location": round(entry_close_location, 6),
            "min_entry_close_location": self.min_entry_close_location,
            "max_entry_momentum_pct": self.max_entry_momentum_pct,
            "entry_momentum_capped": momentum_pct > self.max_entry_momentum_pct,
            "entry_green_body_confirmed": entry_green_body_confirmed,
            "strong_impulse_close_confirmed": strong_impulse_close_confirmed,
            "recent_high_close": round(recent_high_close, 6),
            "breakout_confirmed": breakout_confirmed,
            "buy_threshold_pct": buy_threshold_pct,
            "trend_gap_to_threshold_pct": round(trend_gap_to_threshold_pct, 4),
        }

        if position_open:
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
            reason=(
                f"short_ma={short_ma:.2f}, long_ma={long_ma:.2f}, "
                f"trend_gap_pct={trend_gap_pct:.4f}, momentum_pct={momentum_pct:.4f}"
            ),
            meta=meta,
        )
