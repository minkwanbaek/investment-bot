from investment_bot.market_data.registry import build_default_market_data_registry
from investment_bot.models.market import Candle
from investment_bot.services.market_data_service import MarketDataService


def test_market_data_registry_exposes_mock_and_replay():
    service = MarketDataService(registry=build_default_market_data_registry())
    assert service.list_adapters() == ["mock", "replay"]


def test_mock_market_data_returns_seeded_recent_candles():
    service = MarketDataService(registry=build_default_market_data_registry())
    candles = [
        Candle(symbol="BTC/KRW", timeframe="1h", open=1, high=1, low=1, close=close, volume=1, timestamp=str(i))
        for i, close in enumerate([100, 101, 102, 103, 104], start=1)
    ]
    service.seed_mock(symbol="BTC/KRW", timeframe="1h", candles=candles)

    recent = service.get_recent_candles(adapter_name="mock", symbol="BTC/KRW", timeframe="1h", limit=3)
    assert [item.close for item in recent] == [102, 103, 104]


def test_replay_market_data_advances_cursor():
    service = MarketDataService(registry=build_default_market_data_registry())
    candles = [
        Candle(symbol="BTC/KRW", timeframe="1h", open=1, high=1, low=1, close=close, volume=1, timestamp=str(i))
        for i, close in enumerate([100, 101, 102, 103, 104], start=1)
    ]
    service.load_replay(symbol="BTC/KRW", timeframe="1h", candles=candles)
    service.advance_replay(symbol="BTC/KRW", timeframe="1h", steps=4)

    recent = service.get_recent_candles(adapter_name="replay", symbol="BTC/KRW", timeframe="1h", limit=5)
    assert [item.close for item in recent] == [100, 101, 102, 103, 104]
