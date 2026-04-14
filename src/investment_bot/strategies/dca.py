from investment_bot.models.signal import TradeSignal
from investment_bot.strategies.base import BaseStrategy
from investment_bot.services.paper_broker import PaperBroker


class DCAStrategy(BaseStrategy):
    name = "dca"

    def generate_signal(self, candles, broker: PaperBroker | None = None):
        symbol = candles[-1].symbol if candles else "BTC/KRW"
        closes = [c.close for c in candles]
        if len(closes) < 8:
            return TradeSignal(strategy_name=self.name, symbol=symbol, action="hold", confidence=0.0, reason="insufficient data")
        latest = closes[-1]
        avg = sum(closes[-8:]) / 8
        drawdown_pct = ((latest - avg) / avg) if avg else 0.0
        if drawdown_pct <= -0.02:
            return TradeSignal(strategy_name=self.name, symbol=symbol, action="buy", confidence=0.25, reason=f"value_dca drawdown_pct={drawdown_pct:.4f}")
        return TradeSignal(strategy_name=self.name, symbol=symbol, action="hold", confidence=0.0, reason=f"no_dca_window drawdown_pct={drawdown_pct:.4f}")