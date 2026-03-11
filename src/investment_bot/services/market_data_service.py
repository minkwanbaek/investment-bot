from dataclasses import dataclass

from investment_bot.market_data.mock import MockMarketDataAdapter
from investment_bot.market_data.registry import MarketDataRegistry
from investment_bot.market_data.replay import ReplayMarketDataAdapter
from investment_bot.models.market import Candle
from investment_bot.services.candle_store import CandleStore


@dataclass
class MarketDataService:
    registry: MarketDataRegistry
    candle_store: CandleStore | None = None

    def list_adapters(self) -> list[str]:
        return self.registry.list_names()

    def seed_mock(self, symbol: str, timeframe: str, candles: list[Candle]) -> dict:
        adapter = self.registry.get("mock")
        if not isinstance(adapter, MockMarketDataAdapter):
            raise ValueError("mock adapter unavailable")
        adapter.seed(symbol=symbol, timeframe=timeframe, candles=candles)
        stored = self._store_candles(symbol=symbol, timeframe=timeframe, candles=candles)
        return {"adapter": adapter.name, "symbol": symbol, "timeframe": timeframe, "count": len(candles), "stored": stored}

    def load_replay(self, symbol: str, timeframe: str, candles: list[Candle]) -> dict:
        adapter = self.registry.get("replay")
        if not isinstance(adapter, ReplayMarketDataAdapter):
            raise ValueError("replay adapter unavailable")
        adapter.load(symbol=symbol, timeframe=timeframe, candles=candles)
        stored = self._store_candles(symbol=symbol, timeframe=timeframe, candles=candles)
        return {"adapter": adapter.name, "symbol": symbol, "timeframe": timeframe, "count": len(candles), "stored": stored}

    def advance_replay(self, symbol: str, timeframe: str, steps: int = 1) -> dict:
        adapter = self.registry.get("replay")
        if not isinstance(adapter, ReplayMarketDataAdapter):
            raise ValueError("replay adapter unavailable")
        cursor = adapter.advance(symbol=symbol, timeframe=timeframe, steps=steps)
        return {"adapter": adapter.name, "symbol": symbol, "timeframe": timeframe, "cursor": cursor}

    def _store_candles(self, symbol: str, timeframe: str, candles: list[Candle]) -> dict | None:
        if not self.candle_store:
            return None
        return self.candle_store.append(symbol=symbol, timeframe=timeframe, candles=candles)

    def get_recent_candles(self, adapter_name: str, symbol: str, timeframe: str, limit: int) -> list[Candle]:
        return list(self.registry.get(adapter_name).get_recent_candles(symbol=symbol, timeframe=timeframe, limit=limit))

    def reset_candle_store(self) -> dict:
        if not self.candle_store:
            raise ValueError("candle store unavailable")
        return self.candle_store.reset()

    def export_candle_store(self) -> dict:
        if not self.candle_store:
            raise ValueError("candle store unavailable")
        return self.candle_store.export_state()

    def get_stored_candles(self, symbol: str, timeframe: str, limit: int) -> list[Candle]:
        if not self.candle_store:
            raise ValueError("candle store unavailable")
        return self.candle_store.list_recent(symbol=symbol, timeframe=timeframe, limit=limit)
