from dataclasses import dataclass

from investment_bot.market_data.mock import MockMarketDataAdapter
from investment_bot.market_data.registry import MarketDataRegistry
from investment_bot.market_data.replay import ReplayMarketDataAdapter
from investment_bot.models.market import Candle


@dataclass
class MarketDataService:
    registry: MarketDataRegistry

    def list_adapters(self) -> list[str]:
        return self.registry.list_names()

    def seed_mock(self, symbol: str, timeframe: str, candles: list[Candle]) -> dict:
        adapter = self.registry.get("mock")
        if not isinstance(adapter, MockMarketDataAdapter):
            raise ValueError("mock adapter unavailable")
        adapter.seed(symbol=symbol, timeframe=timeframe, candles=candles)
        return {"adapter": adapter.name, "symbol": symbol, "timeframe": timeframe, "count": len(candles)}

    def load_replay(self, symbol: str, timeframe: str, candles: list[Candle]) -> dict:
        adapter = self.registry.get("replay")
        if not isinstance(adapter, ReplayMarketDataAdapter):
            raise ValueError("replay adapter unavailable")
        adapter.load(symbol=symbol, timeframe=timeframe, candles=candles)
        return {"adapter": adapter.name, "symbol": symbol, "timeframe": timeframe, "count": len(candles)}

    def advance_replay(self, symbol: str, timeframe: str, steps: int = 1) -> dict:
        adapter = self.registry.get("replay")
        if not isinstance(adapter, ReplayMarketDataAdapter):
            raise ValueError("replay adapter unavailable")
        cursor = adapter.advance(symbol=symbol, timeframe=timeframe, steps=steps)
        return {"adapter": adapter.name, "symbol": symbol, "timeframe": timeframe, "cursor": cursor}

    def get_recent_candles(self, adapter_name: str, symbol: str, timeframe: str, limit: int) -> list[Candle]:
        return list(self.registry.get(adapter_name).get_recent_candles(symbol=symbol, timeframe=timeframe, limit=limit))
