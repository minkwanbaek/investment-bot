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
    rising_trend = _candles("RISE/KRW", [100 + i * 0.2 for i in range(30)], [100.0] * 29 + [125.0])
    falling_spike = _candles("FALL/KRW", [110 - i * 0.25 for i in range(30)], [120.0] * 29 + [900.0])

    assert selector._score(rising_trend) > selector._score(falling_spike)


def test_selector_excludes_non_positive_score_symbols():
    class FakeMarketDataService:
        def __init__(self, candles_by_symbol):
            self.candles_by_symbol = candles_by_symbol

        def get_recent_candles(self, adapter_name, symbol, timeframe, limit):
            return self.candles_by_symbol[symbol]

    rising_trend = _candles("RISE/KRW", [100 + i * 0.2 for i in range(30)], [100.0] * 29 + [125.0])
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

    rising_trend = _candles("RISE/KRW", [100 + i * 0.2 for i in range(30)], [100.0] * 29 + [125.0])
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

    rising_trend = _candles("RISE/KRW", [100 + i * 0.2 for i in range(30)], [100.0] * 29 + [125.0])
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


def test_selector_caps_liquidity_so_stronger_breakout_can_rank_first():
    class FakeMarketDataService:
        def __init__(self, candles_by_symbol):
            self.candles_by_symbol = candles_by_symbol

        def get_recent_candles(self, adapter_name, symbol, timeframe, limit):
            return self.candles_by_symbol[symbol]

    liquid_slow = _candles(
        "LIQUID/KRW",
        [100.0 + i * 0.05 for i in range(29)] + [101.6],
        [50_000_000.0] * 29 + [51_000_000.0],
    )
    fast_breakout = _candles(
        "FAST/KRW",
        [100.0 + i * 0.2 for i in range(29)] + [108.5],
        [600_000.0] * 29 + [1_800_000.0],
    )
    selector = DynamicSymbolSelector(
        market_data_service=FakeMarketDataService(
            {
                "LIQUID/KRW": liquid_slow,
                "FAST/KRW": fast_breakout,
            }
        )
    )

    assert selector.select(["LIQUID/KRW", "FAST/KRW"], timeframe="5m", top_n=1) == ["FAST/KRW"]


def test_selector_requires_confirming_volume_for_breakout_candidate():
    class FakeMarketDataService:
        def __init__(self, candles_by_symbol):
            self.candles_by_symbol = candles_by_symbol

        def get_recent_candles(self, adapter_name, symbol, timeframe, limit):
            return self.candles_by_symbol[symbol]

    thin_breakout = _candles(
        "THIN/KRW",
        [100.0 + i * 0.1 for i in range(20)] + [103.0, 104.0, 105.0, 106.0, 107.0, 108.0, 109.0, 110.0, 111.0, 112.0],
        [1000.0] * 29 + [500.0],
    )
    confirmed_breakout = _candles(
        "RUN/KRW",
        [100.0 + i * 0.05 for i in range(22)] + [101.2, 101.4, 101.6, 101.8, 102.0, 102.2, 102.4, 102.7],
        [1000.0] * 29 + [1500.0],
    )
    selector = DynamicSymbolSelector(
        market_data_service=FakeMarketDataService(
            {
                "THIN/KRW": thin_breakout,
                "RUN/KRW": confirmed_breakout,
            }
        )
    )

    thin_return_after_costs = ((109.0 * 0.9995) - (112.0 * 1.0005)) / (112.0 * 1.0005)
    run_return_after_costs = ((106.0 * 0.9995) - (102.7 * 1.0005)) / (102.7 * 1.0005)

    assert selector._score(thin_breakout) > selector._score(confirmed_breakout)
    assert thin_return_after_costs < 0
    assert run_return_after_costs > thin_return_after_costs
    assert selector.select(["THIN/KRW", "RUN/KRW"], timeframe="5m", top_n=1) == ["RUN/KRW"]


def test_selector_requires_volume_surge_for_breakout_candidate():
    class FakeMarketDataService:
        def __init__(self, candles_by_symbol):
            self.candles_by_symbol = candles_by_symbol

        def get_recent_candles(self, adapter_name, symbol, timeframe, limit):
            return self.candles_by_symbol[symbol]

    average_volume_breakout = _candles(
        "AVG/KRW",
        [100.0 + i * 0.08 for i in range(24)] + [101.9, 102.3, 102.8, 103.4, 104.1, 105.5],
        [1000.0] * 29 + [1190.0],
    )
    surge_breakout = _candles(
        "SURGE/KRW",
        [100.0 + i * 0.06 for i in range(24)] + [101.5, 101.7, 101.9, 102.1, 102.4, 102.8],
        [1000.0] * 29 + [1400.0],
    )
    selector = DynamicSymbolSelector(
        market_data_service=FakeMarketDataService(
            {
                "AVG/KRW": average_volume_breakout,
                "SURGE/KRW": surge_breakout,
            }
        )
    )

    avg_return_after_costs = ((103.5 * 0.9995) - (105.5 * 1.0005)) / (105.5 * 1.0005)
    surge_return_after_costs = ((105.2 * 0.9995) - (102.8 * 1.0005)) / (102.8 * 1.0005)

    assert selector._score(average_volume_breakout) > selector._score(surge_breakout)
    assert avg_return_after_costs < 0
    assert surge_return_after_costs > 0
    assert selector.select(["AVG/KRW", "SURGE/KRW"], timeframe="5m", top_n=1) == ["SURGE/KRW"]


def test_selector_requires_two_step_positive_momentum_for_breakout_candidate():
    class FakeMarketDataService:
        def __init__(self, candles_by_symbol):
            self.candles_by_symbol = candles_by_symbol

        def get_recent_candles(self, adapter_name, symbol, timeframe, limit):
            return self.candles_by_symbol[symbol]

    one_bar_spike = _candles(
        "SPIKE/KRW",
        [100.0 + i * 0.08 for i in range(24)] + [102.0, 102.6, 102.4, 102.2, 102.0, 104.5],
        [1000.0] * 29 + [2800.0],
    )
    steady_continuation = _candles(
        "STEADY/KRW",
        [100.0 + i * 0.06 for i in range(24)] + [101.5, 101.8, 102.1, 102.4, 102.8, 103.3],
        [1000.0] * 29 + [1600.0],
    )
    selector = DynamicSymbolSelector(
        market_data_service=FakeMarketDataService(
            {
                "SPIKE/KRW": one_bar_spike,
                "STEADY/KRW": steady_continuation,
            }
        )
    )

    spike_return_after_costs = ((101.8 * 0.9995) - (104.5 * 1.0005)) / (104.5 * 1.0005)
    steady_return_after_costs = ((105.4 * 0.9995) - (103.3 * 1.0005)) / (103.3 * 1.0005)

    assert selector._score(one_bar_spike) > selector._score(steady_continuation)
    assert spike_return_after_costs < 0
    assert steady_return_after_costs > 0
    assert selector.select(["SPIKE/KRW", "STEADY/KRW"], timeframe="5m", top_n=1) == ["STEADY/KRW"]


def test_selector_requires_strong_close_location_for_breakout_candidate():
    class FakeMarketDataService:
        def __init__(self, candles_by_symbol):
            self.candles_by_symbol = candles_by_symbol

        def get_recent_candles(self, adapter_name, symbol, timeframe, limit):
            return self.candles_by_symbol[symbol]

    wick_fakeout = _candles(
        "WICK/KRW",
        [100.0 + i * 0.08 for i in range(24)] + [102.0, 102.5, 103.0, 103.5, 104.0, 105.0],
        [1000.0] * 29 + [3000.0],
    )
    wick_fakeout[-1].low = 104.0
    wick_fakeout[-1].high = 111.0
    wick_fakeout[-1].open = 104.3
    clean_continuation = _candles(
        "CLEAN/KRW",
        [100.0 + i * 0.06 for i in range(24)] + [101.5, 101.8, 102.1, 102.4, 102.8, 103.4],
        [1000.0] * 29 + [1500.0],
    )
    clean_continuation[-1].low = 102.9
    clean_continuation[-1].high = 103.5
    clean_continuation[-1].open = 103.0
    selector = DynamicSymbolSelector(
        market_data_service=FakeMarketDataService(
            {
                "WICK/KRW": wick_fakeout,
                "CLEAN/KRW": clean_continuation,
            }
        )
    )

    wick_return_after_costs = ((103.0 * 0.9995) - (105.0 * 1.0005)) / (105.0 * 1.0005)
    clean_return_after_costs = ((105.8 * 0.9995) - (103.4 * 1.0005)) / (103.4 * 1.0005)

    assert selector._score(wick_fakeout) > selector._score(clean_continuation)
    assert selector._has_positive_short_momentum(wick_fakeout)
    assert selector._has_confirming_volume(wick_fakeout)
    assert not selector._has_breakout_close_location(wick_fakeout)
    assert wick_return_after_costs < 0
    assert clean_return_after_costs > 0
    assert selector.select(["WICK/KRW", "CLEAN/KRW"], timeframe="5m", top_n=1) == ["CLEAN/KRW"]
