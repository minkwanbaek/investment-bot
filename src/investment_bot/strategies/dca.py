from investment_bot.models.signal import TradeSignal
from investment_bot.strategies.base import BaseStrategy
from investment_bot.services.paper_broker import PaperBroker


class DCAStrategy(BaseStrategy):
    name = "dca"
    buy_drawdown_threshold = -0.016
    max_buy_drawdown_pct = -0.06
    sell_rebound_threshold = 0.008

    def generate_signal(self, candles, broker: PaperBroker | None = None):
        symbol = candles[-1].symbol if candles else "BTC/KRW"
        closes = [c.close for c in candles]
        if len(closes) < 8:
            return TradeSignal(strategy_name=self.name, symbol=symbol, action="hold", confidence=0.0, reason="insufficient data")
        latest = closes[-1]
        position = (broker.positions.get(symbol) if broker else None) or {}
        position_qty = float(position.get("quantity", 0.0) or 0.0)
        average_price = float(position.get("average_price", 0.0) or 0.0)
        rebound_pct = ((latest - average_price) / average_price) if average_price else 0.0
        if position_qty > 0 and rebound_pct >= self.sell_rebound_threshold:
            return TradeSignal(strategy_name=self.name, symbol=symbol, action="sell", confidence=0.60, reason=f"value_dca_rebound_exit rebound_pct={rebound_pct:.4f}")
        avg = sum(closes[-8:]) / 8
        drawdown_pct = ((latest - avg) / avg) if avg else 0.0
        prev = closes[-2]
        momentum_pct = ((latest - prev) / prev) if prev else 0.0
        body_confirmed = candles[-1].close >= candles[-1].open
        if self.max_buy_drawdown_pct <= drawdown_pct <= self.buy_drawdown_threshold and momentum_pct >= 0 and body_confirmed:
            return TradeSignal(strategy_name=self.name, symbol=symbol, action="buy", confidence=0.50, reason=f"value_dca drawdown_pct={drawdown_pct:.4f}, momentum_pct={momentum_pct:.4f}, body_confirmed={body_confirmed}")
        return TradeSignal(strategy_name=self.name, symbol=symbol, action="hold", confidence=0.0, reason=f"no_dca_window drawdown_pct={drawdown_pct:.4f}, momentum_pct={momentum_pct:.4f}, body_confirmed={body_confirmed}")
