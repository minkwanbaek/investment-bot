from statistics import mean
from investment_bot.models.signal import TradeSignal
from investment_bot.strategies.base import BaseStrategy


class TrendFollowingStrategy(BaseStrategy):
    name = "trend_following"
    min_trend_gap_pct = 0.0015  # 0.15%
    
    # 청산 조건
    stop_loss_pct = -0.02  # -2%
    take_profit_pct = 0.05  # +5%

    def generate_signal(self, candles, broker=None):
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
        
        # Near-miss observability: structured metrics
        buy_threshold_pct = self.min_trend_gap_pct
        trend_gap_to_threshold_pct = trend_gap_pct / buy_threshold_pct if buy_threshold_pct > 0 else 0.0

        # 포지션이 있으면 청산 조건 먼저 체크
        if broker is not None:
            position = broker.positions.get(symbol, {})
            quantity = position.get("quantity", 0.0)
            if quantity > 0:
                average_price = position.get("average_price", 0.0)
                current_price = latest
                
                if average_price > 0:
                    pnl_pct = (current_price - average_price) / average_price
                    
                    # Stop Loss: -2% 이하
                    if pnl_pct <= self.stop_loss_pct:
                        return TradeSignal(
                            strategy_name=self.name,
                            symbol=symbol,
                            action="sell",
                            confidence=1.0,
                            reason=f"stop_loss: pnl={pnl_pct*100:.2f}%, avg_price={average_price:,.0f}, current={current_price:,.0f}",
                            meta={"force_exit": True, "exit_reason": "stop_loss"},
                        )
                    
                    # Take Profit: +5% 이상
                    if pnl_pct >= self.take_profit_pct:
                        return TradeSignal(
                            strategy_name=self.name,
                            symbol=symbol,
                            action="sell",
                            confidence=1.0,
                            reason=f"take_profit: pnl={pnl_pct*100:.2f}%, avg_price={average_price:,.0f}, current={current_price:,.0f}",
                            meta={"force_exit": True, "exit_reason": "take_profit"},
                        )
                    
                    # Trend Reversal: short_ma < long_ma
                    if short_ma < long_ma:
                        return TradeSignal(
                            strategy_name=self.name,
                            symbol=symbol,
                            action="sell",
                            confidence=0.8,
                            reason=f"trend_reversal: short_ma={short_ma:.2f} < long_ma={long_ma:.2f}, pnl={pnl_pct*100:.2f}%",
                            meta={"force_exit": True, "exit_reason": "trend_reversal"},
                        )

        # 진입 신호 로직
        if trend_gap_pct >= self.min_trend_gap_pct and momentum_pct > 0:
            action = "buy"
        elif trend_gap_pct <= -self.min_trend_gap_pct and momentum_pct < 0:
            action = "sell"
        else:
            action = "hold"

        confidence = min(max(abs(trend_gap_pct) * 120, 0.0), 1.0)
        
        # Near-miss observability: structured meta
        meta = {
            "trend_gap_pct": round(trend_gap_pct, 6),
            "momentum_pct": round(momentum_pct, 6),
            "buy_threshold_pct": buy_threshold_pct,
            "trend_gap_to_threshold_pct": round(trend_gap_to_threshold_pct, 4),
        }
        
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
