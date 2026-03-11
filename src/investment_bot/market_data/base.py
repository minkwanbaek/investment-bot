from abc import ABC, abstractmethod
from typing import Sequence

from investment_bot.models.market import Candle


class MarketDataAdapter(ABC):
    name: str

    @abstractmethod
    def get_recent_candles(self, symbol: str, timeframe: str, limit: int) -> Sequence[Candle]:
        raise NotImplementedError
