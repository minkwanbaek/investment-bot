from investment_bot.models.signal import TradeSignal
from investment_bot.strategies.base import BaseStrategy

class DCAStrategy(BaseStrategy):
    name = "dca"

    def generate_signal(self, candles):
        symbol = candles[-1].symbol if candles else "BTC/KRW"
        return TradeSignal(strategy_name=self.name, symbol=symbol, action="buy", confidence=0.2, reason="scheduled accumulation placeholder")
