from investment_bot.market_data.base import MarketDataAdapter
from investment_bot.market_data.live import LiveMarketDataAdapter
from investment_bot.market_data.mock import MockMarketDataAdapter
from investment_bot.market_data.replay import ReplayMarketDataAdapter


class MarketDataRegistry:
    def __init__(self):
        self._adapters: dict[str, MarketDataAdapter] = {}

    def register(self, adapter: MarketDataAdapter) -> None:
        self._adapters[adapter.name] = adapter

    def get(self, name: str) -> MarketDataAdapter:
        adapter = self._adapters.get(name)
        if adapter is None:
            raise ValueError(f"unknown market data adapter: {name}")
        return adapter

    def list_names(self) -> list[str]:
        return sorted(self._adapters.keys())


def build_default_market_data_registry() -> MarketDataRegistry:
    registry = MarketDataRegistry()
    registry.register(MockMarketDataAdapter())
    registry.register(ReplayMarketDataAdapter())
    registry.register(LiveMarketDataAdapter())
    return registry
