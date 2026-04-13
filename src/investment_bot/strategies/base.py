from abc import ABC, abstractmethod
from typing import Sequence
from investment_bot.models.market import Candle
from investment_bot.models.signal import TradeSignal
from investment_bot.services.paper_broker import PaperBroker

class BaseStrategy(ABC):
    name: str

    @abstractmethod
    def generate_signal(self, candles: Sequence[Candle], broker: PaperBroker | None = None) -> TradeSignal:
        raise NotImplementedError
