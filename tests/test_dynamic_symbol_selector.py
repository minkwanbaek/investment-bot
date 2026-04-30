from investment_bot.models.market import Candle
from investment_bot.services.dynamic_symbol_selector import DynamicSymbolSelector


def _candles(symbol: str, closes: list[float], volumes: list[float]) -> list[Candle]:
    return [
        Candle(
            symbol=symbol,
            timeframe="5m",
            open=close,
            high=close,
            low=close,
            close=close,
            volume=volume,
            timestamp=str(i),
        )
        for i, (close, volume) in enumerate(zip(closes, volumes))
    ]


def test_selector_prefers_positive_momentum_over_falling_volume_spike():
    selector = DynamicSymbolSelector(market_data_service=None)
    rising_trend = _candles("RISE/KRW", [100 + i * 0.2 for i in range(30)], [100.0] * 30)
    falling_spike = _candles("FALL/KRW", [110 - i * 0.25 for i in range(30)], [120.0] * 29 + [900.0])

    assert selector._score(rising_trend) > selector._score(falling_spike)


def test_selector_excludes_non_positive_score_symbols():
    class FakeMarketDataService:
        def __init__(self, candles_by_symbol):
            self.candles_by_symbol = candles_by_symbol

        def get_recent_candles(self, adapter_name, symbol, timeframe, limit):
            return self.candles_by_symbol[symbol]

    rising_trend = _candles("RISE/KRW", [100 + i * 0.2 for i in range(30)], [100.0] * 30)
    falling_trend = _candles("FALL/KRW", [110 - i * 0.25 for i in range(30)], [120.0] * 29 + [900.0])
    selector = DynamicSymbolSelector(
        market_data_service=FakeMarketDataService(
            {
                "RISE/KRW": rising_trend,
                "FALL/KRW": falling_trend,
            }
        )
    )

    assert selector.select(["RISE/KRW", "FALL/KRW"], timeframe="5m", top_n=2) == ["RISE/KRW"]


def test_selector_returns_empty_when_all_symbols_score_non_positive():
    class FakeMarketDataService:
        def __init__(self, candles_by_symbol):
            self.candles_by_symbol = candles_by_symbol

        def get_recent_candles(self, adapter_name, symbol, timeframe, limit):
            return self.candles_by_symbol[symbol]

    weak_trend = _candles("WEAK/KRW", [110 - i * 0.2 for i in range(30)], [100.0] * 30)
    falling_spike = _candles("FALL/KRW", [110 - i * 0.25 for i in range(30)], [120.0] * 29 + [900.0])
    selector = DynamicSymbolSelector(
        market_data_service=FakeMarketDataService(
            {
                "WEAK/KRW": weak_trend,
                "FALL/KRW": falling_spike,
            }
        )
    )

    assert selector.select(["WEAK/KRW", "FALL/KRW"], timeframe="5m", top_n=2) == []


def test_selector_excludes_positive_score_symbol_with_negative_short_momentum():
    class FakeMarketDataService:
        def __init__(self, candles_by_symbol):
            self.candles_by_symbol = candles_by_symbol

        def get_recent_candles(self, adapter_name, symbol, timeframe, limit):
            return self.candles_by_symbol[symbol]

    rising_trend = _candles("RISE/KRW", [100 + i * 0.2 for i in range(30)], [100.0] * 30)
    fading_trend = _candles(
        "FADE/KRW",
        [100 + i * 0.35 for i in range(29)] + [109.7],
        [500.0] * 30,
    )
    selector = DynamicSymbolSelector(
        market_data_service=FakeMarketDataService(
            {
                "RISE/KRW": rising_trend,
                "FADE/KRW": fading_trend,
            }
        )
    )

    assert selector._score(fading_trend) > 0
    assert selector.select(["RISE/KRW", "FADE/KRW"], timeframe="5m", top_n=2) == ["RISE/KRW"]


def test_selector_excludes_positive_score_fading_bounce():
    class FakeMarketDataService:
        def __init__(self, candles_by_symbol):
            self.candles_by_symbol = candles_by_symbol

        def get_recent_candles(self, adapter_name, symbol, timeframe, limit):
            return self.candles_by_symbol[symbol]

    rising_trend = _candles("RISE/KRW", [100 + i * 0.2 for i in range(30)], [100.0] * 30)
    fading_bounce = _candles(
        "BOUNCE/KRW",
        [100 + i * 0.4 for i in range(27)] + [110.4, 108.0, 108.2],
        [450.0] * 30,
    )
    selector = DynamicSymbolSelector(
        market_data_service=FakeMarketDataService(
            {
                "RISE/KRW": rising_trend,
                "BOUNCE/KRW": fading_bounce,
            }
        )
    )

    assert selector._score(fading_bounce) > 0
    assert fading_bounce[-1].close > fading_bounce[-2].close
    assert selector.select(["RISE/KRW", "BOUNCE/KRW"], timeframe="5m", top_n=2) == ["RISE/KRW"]


def test_selector_requires_short_recent_high_breakout():
    class FakeMarketDataService:
        def __init__(self, candles_by_symbol):
            self.candles_by_symbol = candles_by_symbol

        def get_recent_candles(self, adapter_name, symbol, timeframe, limit):
            return self.candles_by_symbol[symbol]

    breakout = _candles(
        "BREAK/KRW",
        [100.0 + i * 0.15 for i in range(22)] + [104.0, 104.2, 104.4, 104.6, 104.8, 105.0, 105.2, 105.8],
        [100.0] * 29 + [120.0],
    )
    lower_high = _candles(
        "LOWER/KRW",
        [100.0 + i * 0.1 for i in range(22)] + [110.0, 108.0, 107.0, 106.0, 105.0, 105.4, 105.8, 106.2],
        [800.0] * 29 + [4000.0],
    )
    selector = DynamicSymbolSelector(
        market_data_service=FakeMarketDataService(
            {
                "BREAK/KRW": breakout,
                "LOWER/KRW": lower_high,
            }
        )
    )

    assert selector._score(lower_high) > selector._score(breakout)
    assert lower_high[-1].close > lower_high[-2].close
    assert lower_high[-1].close < max(c.close for c in lower_high[-8:-1])
    assert selector.select(["LOWER/KRW", "BREAK/KRW"], timeframe="5m", top_n=1) == ["BREAK/KRW"]
