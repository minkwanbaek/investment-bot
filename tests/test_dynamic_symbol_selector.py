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
    rising_trend = _candles("RISE/KRW", [100 + i * 0.2 for i in range(30)], [100.0] * 29 + [140.0])
    falling_spike = _candles("FALL/KRW", [110 - i * 0.25 for i in range(30)], [120.0] * 29 + [900.0])

    assert selector._score(rising_trend) > selector._score(falling_spike)


def test_selector_fills_remaining_top_n_with_soft_breakout_candidates():
    class FakeMarketDataService:
        def __init__(self, candles_by_symbol):
            self.candles_by_symbol = candles_by_symbol

        def get_recent_candles(self, adapter_name, symbol, timeframe, limit):
            return self.candles_by_symbol[symbol]

    strict_breakout = _candles(
        "STRICT/KRW",
        [100.0 + i * 0.06 for i in range(24)] + [101.4, 101.7, 102.0, 102.3, 102.7, 103.2],
        [1000.0] * 29 + [1500.0],
    )
    soft_breakout = _candles(
        "SOFT/KRW",
        [100.0 + i * 0.06 for i in range(24)] + [101.5, 101.8, 102.1, 102.4, 102.8, 103.3],
        [1000.0] * 29 + [1500.0],
    )
    soft_breakout[-1].low = 102.8
    soft_breakout[-1].high = 103.9
    soft_breakout[-1].open = 102.95

    selector = DynamicSymbolSelector(
        market_data_service=FakeMarketDataService(
            {
                "STRICT/KRW": strict_breakout,
                "SOFT/KRW": soft_breakout,
            }
        )
    )

    assert selector._has_breakout_close_location(strict_breakout)
    assert not selector._has_breakout_close_location(soft_breakout)
    assert selector.select(["STRICT/KRW", "SOFT/KRW"], timeframe="5m", top_n=1) == ["STRICT/KRW"]
    assert selector.select(["STRICT/KRW", "SOFT/KRW"], timeframe="5m", top_n=2) == ["STRICT/KRW", "SOFT/KRW"]


def test_selector_excludes_non_positive_score_symbols():
    class FakeMarketDataService:
        def __init__(self, candles_by_symbol):
            self.candles_by_symbol = candles_by_symbol

        def get_recent_candles(self, adapter_name, symbol, timeframe, limit):
            return self.candles_by_symbol[symbol]

    rising_trend = _candles("RISE/KRW", [100 + i * 0.2 for i in range(30)], [100.0] * 29 + [140.0])
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


def test_selector_includes_stabilizing_oversold_range_rebound():
    class FakeMarketDataService:
        def __init__(self, candles_by_symbol):
            self.candles_by_symbol = candles_by_symbol

        def get_recent_candles(self, adapter_name, symbol, timeframe, limit):
            return self.candles_by_symbol[symbol]

    flat = _candles("FLAT/KRW", [100.0] * 30, [100.0] * 30)
    rebound = _candles(
        "ONDO/KRW",
        [100.0] * 22 + [100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 94.0, 95.0],
        [100.0] * 29 + [130.0],
    )
    selector = DynamicSymbolSelector(
        market_data_service=FakeMarketDataService(
            {
                "FLAT/KRW": flat,
                "ONDO/KRW": rebound,
            }
        )
    )

    assert not selector._has_positive_short_momentum(rebound)
    assert selector._range_rebound_score(rebound) > 0
    assert selector.select(["FLAT/KRW", "ONDO/KRW"], timeframe="5m", top_n=1) == ["ONDO/KRW"]


def test_selector_includes_shallow_range_rebound_after_mean_reversion_gate():
    class FakeMarketDataService:
        def __init__(self, candles_by_symbol):
            self.candles_by_symbol = candles_by_symbol

        def get_recent_candles(self, adapter_name, symbol, timeframe, limit):
            return self.candles_by_symbol[symbol]

    flat = _candles("FLAT/KRW", [100.0] * 30, [100.0] * 30)
    shallow_rebound = _candles(
        "ONDO/KRW",
        [100.0] * 22 + [100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 95.7, 96.5],
        [100.0] * 29 + [130.0],
    )
    baseline_selector = DynamicSymbolSelector(
        market_data_service=FakeMarketDataService({"FLAT/KRW": flat, "ONDO/KRW": shallow_rebound}),
        min_range_rebound_discount_pct=0.03,
    )
    candidate_selector = DynamicSymbolSelector(
        market_data_service=FakeMarketDataService({"FLAT/KRW": flat, "ONDO/KRW": shallow_rebound})
    )

    assert baseline_selector.select(["FLAT/KRW", "ONDO/KRW"], timeframe="5m", top_n=1) == []
    assert candidate_selector._range_rebound_score(shallow_rebound) > 0
    assert candidate_selector.select(["FLAT/KRW", "ONDO/KRW"], timeframe="5m", top_n=1) == ["ONDO/KRW"]


def test_selector_includes_dca_1p6pct_range_rebound():
    class FakeMarketDataService:
        def __init__(self, candles_by_symbol):
            self.candles_by_symbol = candles_by_symbol

        def get_recent_candles(self, adapter_name, symbol, timeframe, limit):
            return self.candles_by_symbol[symbol]

    flat = _candles("FLAT/KRW", [100.0] * 30, [100.0] * 30)
    dca_rebound = _candles(
        "ONDO/KRW",
        [100.0] * 22 + [100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 97.5, 97.8],
        [100.0] * 29 + [130.0],
    )
    baseline_selector = DynamicSymbolSelector(
        market_data_service=FakeMarketDataService({"FLAT/KRW": flat, "ONDO/KRW": dca_rebound}),
        min_range_rebound_discount_pct=0.018,
    )
    candidate_selector = DynamicSymbolSelector(
        market_data_service=FakeMarketDataService({"FLAT/KRW": flat, "ONDO/KRW": dca_rebound})
    )

    assert baseline_selector.select(["FLAT/KRW", "ONDO/KRW"], timeframe="5m", top_n=1) == []
    assert candidate_selector._range_rebound_score(dca_rebound) > 0
    assert candidate_selector.select(["FLAT/KRW", "ONDO/KRW"], timeframe="5m", top_n=1) == ["ONDO/KRW"]


def test_selector_skips_red_body_range_rebound_for_green_actionable_rebound():
    class FakeMarketDataService:
        def __init__(self, candles_by_symbol):
            self.candles_by_symbol = candles_by_symbol

        def get_recent_candles(self, adapter_name, symbol, timeframe, limit):
            return self.candles_by_symbol[symbol]

    red_body_rebound = _candles(
        "RED/KRW",
        [100.0] * 22 + [100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 96.0, 97.0],
        [100.0] * 29 + [150.0],
    )
    red_body_rebound[-1].open = 97.4
    green_body_rebound = _candles(
        "GREEN/KRW",
        [100.0] * 22 + [100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 97.5, 97.8],
        [100.0] * 29 + [130.0],
    )
    green_body_rebound[-1].open = 97.6
    selector = DynamicSymbolSelector(
        market_data_service=FakeMarketDataService(
            {
                "RED/KRW": red_body_rebound,
                "GREEN/KRW": green_body_rebound,
            }
        )
    )

    assert selector._range_rebound_score(red_body_rebound) == 0.0
    assert selector._range_rebound_score(green_body_rebound) > 0
    assert selector.select(["RED/KRW", "GREEN/KRW"], timeframe="5m", top_n=1) == ["GREEN/KRW"]


def test_selector_skips_zero_momentum_range_rebound_for_actionable_rebound():
    class FakeMarketDataService:
        def __init__(self, candles_by_symbol):
            self.candles_by_symbol = candles_by_symbol

        def get_recent_candles(self, adapter_name, symbol, timeframe, limit):
            return self.candles_by_symbol[symbol]

    flat_bottom = _candles(
        "FLATBOTTOM/KRW",
        [100.0] * 22 + [100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 94.0, 94.0],
        [100.0] * 29 + [300.0],
    )
    actionable_rebound = _candles(
        "REBOUND/KRW",
        [100.0] * 22 + [100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 97.5, 97.8],
        [100.0] * 29 + [130.0],
    )
    selector = DynamicSymbolSelector(
        market_data_service=FakeMarketDataService(
            {
                "FLATBOTTOM/KRW": flat_bottom,
                "REBOUND/KRW": actionable_rebound,
            }
        )
    )

    assert selector._range_rebound_score(flat_bottom) == 0.0
    assert selector._range_rebound_score(actionable_rebound) > 0
    assert selector.select(["FLATBOTTOM/KRW", "REBOUND/KRW"], timeframe="5m", top_n=1) == ["REBOUND/KRW"]


def test_selector_includes_volume_confirmed_range_rebound_after_mean_reversion_gate():
    class FakeMarketDataService:
        def __init__(self, candles_by_symbol):
            self.candles_by_symbol = candles_by_symbol

        def get_recent_candles(self, adapter_name, symbol, timeframe, limit):
            return self.candles_by_symbol[symbol]

    flat = _candles("FLAT/KRW", [100.0] * 30, [100.0] * 30)
    volume_confirmed_rebound = _candles(
        "ONDO/KRW",
        [100.0] * 22 + [100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 94.0, 95.0],
        [100.0] * 29 + [105.0],
    )
    baseline_selector = DynamicSymbolSelector(
        market_data_service=FakeMarketDataService({"FLAT/KRW": flat, "ONDO/KRW": volume_confirmed_rebound}),
        min_range_rebound_volume_surge=1.10,
    )
    candidate_selector = DynamicSymbolSelector(
        market_data_service=FakeMarketDataService({"FLAT/KRW": flat, "ONDO/KRW": volume_confirmed_rebound})
    )

    assert baseline_selector.select(["FLAT/KRW", "ONDO/KRW"], timeframe="5m", top_n=1) == []
    assert candidate_selector._range_rebound_score(volume_confirmed_rebound) > 0
    assert candidate_selector.select(["FLAT/KRW", "ONDO/KRW"], timeframe="5m", top_n=1) == ["ONDO/KRW"]


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

    rising_trend = _candles("RISE/KRW", [100 + i * 0.2 for i in range(30)], [100.0] * 29 + [140.0])
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

    rising_trend = _candles("RISE/KRW", [100 + i * 0.2 for i in range(30)], [100.0] * 29 + [140.0])
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
        [100.0] * 29 + [140.0],
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

    assert selector._score(fast_breakout) > selector._score(liquid_slow)
    assert selector._has_confirming_volume(fast_breakout)
    assert not selector._has_controlled_recent_runup(fast_breakout)
    assert selector.select(["LIQUID/KRW", "FAST/KRW"], timeframe="5m", top_n=1) == []


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


def test_selector_volume_gate_1p35_includes_actionable_breakout():
    class FakeMarketDataService:
        def __init__(self, candles_by_symbol):
            self.candles_by_symbol = candles_by_symbol

        def get_recent_candles(self, adapter_name, symbol, timeframe, limit):
            return self.candles_by_symbol[symbol]

    marginal_continuation = _candles(
        "MARGIN/KRW",
        [100.0 + i * 0.05 for i in range(24)] + [101.4, 101.7, 102.0, 102.3, 102.7, 103.1],
        [1000.0] * 29 + [1360.0],
    )
    flat = _candles("FLAT/KRW", [100.0] * 30, [1000.0] * 30)
    market_data_service = FakeMarketDataService(
        {
            "MARGIN/KRW": marginal_continuation,
            "FLAT/KRW": flat,
        }
    )
    baseline_selector = DynamicSymbolSelector(market_data_service=market_data_service, min_confirming_volume_surge=1.40)
    candidate_selector = DynamicSymbolSelector(market_data_service=market_data_service)

    assert baseline_selector.select(["MARGIN/KRW", "FLAT/KRW"], timeframe="5m", top_n=1) == []
    assert candidate_selector._has_confirming_volume(marginal_continuation)
    assert candidate_selector.select(["MARGIN/KRW", "FLAT/KRW"], timeframe="5m", top_n=1) == ["MARGIN/KRW"]


def test_selector_volume_gate_1p31_includes_near_strategy_volume_breakout():
    class FakeMarketDataService:
        def __init__(self, candles_by_symbol):
            self.candles_by_symbol = candles_by_symbol

        def get_recent_candles(self, adapter_name, symbol, timeframe, limit):
            return self.candles_by_symbol[symbol]

    marginal_continuation = _candles(
        "MARGIN/KRW",
        [100.0 + i * 0.05 for i in range(24)] + [101.4, 101.7, 102.0, 102.3, 102.7, 103.1],
        [1000.0] * 29 + [1310.0],
    )
    flat = _candles("FLAT/KRW", [100.0] * 30, [1000.0] * 30)
    market_data_service = FakeMarketDataService(
        {
            "MARGIN/KRW": marginal_continuation,
            "FLAT/KRW": flat,
        }
    )
    baseline_selector = DynamicSymbolSelector(market_data_service=market_data_service, min_confirming_volume_surge=1.35)
    candidate_selector = DynamicSymbolSelector(market_data_service=market_data_service)

    assert baseline_selector.select(["MARGIN/KRW", "FLAT/KRW"], timeframe="5m", top_n=1) == []
    assert candidate_selector._has_confirming_volume(marginal_continuation)
    assert candidate_selector.select(["MARGIN/KRW", "FLAT/KRW"], timeframe="5m", top_n=1) == ["MARGIN/KRW"]


def test_selector_rejects_single_candle_pump_over_2p8pct():
    class FakeMarketDataService:
        def __init__(self, candles_by_symbol):
            self.candles_by_symbol = candles_by_symbol

        def get_recent_candles(self, adapter_name, symbol, timeframe, limit):
            return self.candles_by_symbol[symbol]

    pump = _candles(
        "PUMP/KRW",
        [100.0 + i * 0.04 for i in range(26)] + [101.1, 101.3, 101.5, 104.4],
        [1000.0] * 29 + [2200.0],
    )
    controlled = _candles(
        "CTRL/KRW",
        [100.0 + i * 0.04 for i in range(26)] + [101.0, 101.2, 101.4, 104.2],
        [1000.0] * 29 + [2200.0],
    )
    selector = DynamicSymbolSelector(
        market_data_service=FakeMarketDataService(
            {
                "PUMP/KRW": pump,
                "CTRL/KRW": controlled,
            }
        )
    )

    old_selector = DynamicSymbolSelector(
        market_data_service=selector.market_data_service,
        max_breakout_momentum_pct=0.03,
    )
    pump_momentum_pct = (pump[-1].close - pump[-2].close) / pump[-2].close
    controlled_momentum_pct = (controlled[-1].close - controlled[-2].close) / controlled[-2].close
    pump_return_after_costs = ((102.2 * 0.9995) - (103.6 * 1.0005)) / (103.6 * 1.0005)
    controlled_return_after_costs = ((105.0 * 0.9995) - (103.2 * 1.0005)) / (103.2 * 1.0005)

    assert 0.028 < pump_momentum_pct < 0.03
    assert controlled_momentum_pct <= 0.028
    assert pump_return_after_costs < 0
    assert controlled_return_after_costs > 0
    assert not old_selector._has_controlled_recent_runup(pump)
    assert old_selector.select(["PUMP/KRW", "CTRL/KRW"], timeframe="5m", top_n=2)[0] == "CTRL/KRW"
    assert selector.select(["PUMP/KRW", "CTRL/KRW"], timeframe="5m", top_n=2) == ["CTRL/KRW"]


def test_selector_tighter_volume_surge_skips_marginal_breakout_reversal():
    class FakeMarketDataService:
        def __init__(self, candles_by_symbol):
            self.candles_by_symbol = candles_by_symbol

        def get_recent_candles(self, adapter_name, symbol, timeframe, limit):
            return self.candles_by_symbol[symbol]

    marginal_breakout = _candles(
        "MARGINAL/KRW",
        [100.0 + i * 0.08 for i in range(24)] + [102.0, 102.4, 102.9, 103.5, 104.1, 105.2],
        [1000.0] * 29 + [1300.0],
    )
    confirmed_continuation = _candles(
        "CONFIRM/KRW",
        [100.0 + i * 0.06 for i in range(24)] + [101.5, 101.8, 102.1, 102.5, 102.9, 103.4],
        [1000.0] * 29 + [1400.0],
    )
    market_data_service = FakeMarketDataService(
        {
            "MARGINAL/KRW": marginal_breakout,
            "CONFIRM/KRW": confirmed_continuation,
        }
    )
    baseline_selector = DynamicSymbolSelector(market_data_service=market_data_service, min_confirming_volume_surge=1.25)
    candidate_selector = DynamicSymbolSelector(market_data_service=market_data_service)

    marginal_return_after_costs = ((103.1 * 0.9995) - (105.2 * 1.0005)) / (105.2 * 1.0005)
    confirm_return_after_costs = ((105.7 * 0.9995) - (103.4 * 1.0005)) / (103.4 * 1.0005)

    assert baseline_selector._score(marginal_breakout) > baseline_selector._score(confirmed_continuation)
    assert baseline_selector._has_confirming_volume(marginal_breakout)
    assert not candidate_selector._has_confirming_volume(marginal_breakout)
    assert candidate_selector._has_confirming_volume(confirmed_continuation)
    assert marginal_return_after_costs < 0
    assert confirm_return_after_costs > 0
    assert baseline_selector.select(["MARGINAL/KRW", "CONFIRM/KRW"], timeframe="5m", top_n=1) == ["MARGINAL/KRW"]
    assert candidate_selector.select(["MARGINAL/KRW", "CONFIRM/KRW"], timeframe="5m", top_n=1) == ["CONFIRM/KRW"]


def test_selector_volume_window_matches_trend_entry_gate_for_actionable_breakout():
    from investment_bot.strategies.trend_following import TrendFollowingStrategy

    class FakeMarketDataService:
        def __init__(self, candles_by_symbol):
            self.candles_by_symbol = candles_by_symbol

        def get_recent_candles(self, adapter_name, symbol, timeframe, limit):
            return self.candles_by_symbol[symbol]

    stale_volume_breakout = _candles(
        "STALE/KRW",
        [100.0 + i * 0.05 for i in range(24)] + [101.4, 101.8, 102.2, 102.7, 103.3, 104.0],
        [1000.0] * 20 + [500.0, 500.0] + [1100.0] * 7 + [1400.0],
    )
    actionable_breakout = _candles(
        "ACTION/KRW",
        [100.0 + i * 0.04 for i in range(24)] + [101.2, 101.5, 101.8, 102.2, 102.6, 103.1],
        [1000.0] * 29 + [1500.0],
    )
    selector = DynamicSymbolSelector(
        market_data_service=FakeMarketDataService(
            {
                "STALE/KRW": stale_volume_breakout,
                "ACTION/KRW": actionable_breakout,
            }
        )
    )

    old_stale_window = [c.volume for c in stale_volume_breakout[-10:]]
    old_stale_avg = sum(old_stale_window[:-1]) / len(old_stale_window[:-1])
    strategy = TrendFollowingStrategy()

    assert old_stale_window[-1] >= old_stale_avg * selector.min_confirming_volume_surge
    assert not selector._has_confirming_volume(stale_volume_breakout)
    assert selector._has_confirming_volume(actionable_breakout)
    assert strategy.generate_signal(stale_volume_breakout).action == "hold"
    assert strategy.generate_signal(actionable_breakout).action == "buy"
    assert selector.select(["STALE/KRW", "ACTION/KRW"], timeframe="5m", top_n=1) == ["ACTION/KRW"]


def test_selector_default_volume_gate_tracks_trend_following_default(monkeypatch):
    from investment_bot.strategies.trend_following import TrendFollowingStrategy

    class FakeMarketDataService:
        def get_recent_candles(self, adapter_name, symbol, timeframe, limit):
            return []

    monkeypatch.setattr(TrendFollowingStrategy, "min_entry_volume_ratio", 1.42)

    selector = DynamicSymbolSelector(market_data_service=FakeMarketDataService())
    overridden = DynamicSymbolSelector(market_data_service=FakeMarketDataService(), min_confirming_volume_surge=1.25)

    assert selector.min_confirming_volume_surge == 1.42
    assert overridden.min_confirming_volume_surge == 1.25


def test_selector_default_trend_gap_tracks_trend_following_default(monkeypatch):
    from investment_bot.strategies.trend_following import TrendFollowingStrategy

    class FakeMarketDataService:
        def get_recent_candles(self, adapter_name, symbol, timeframe, limit):
            return []

    monkeypatch.setattr(TrendFollowingStrategy, "min_trend_gap_pct", 0.0009)

    selector = DynamicSymbolSelector(market_data_service=FakeMarketDataService())
    overridden = DynamicSymbolSelector(market_data_service=FakeMarketDataService(), min_breakout_trend_gap_pct=0.0014)

    assert selector.min_breakout_trend_gap_pct == 0.0009
    assert overridden.min_breakout_trend_gap_pct == 0.0014


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


def test_selector_allows_flat_then_breakout_positive_momentum_when_strategy_would_buy():
    from investment_bot.strategies.trend_following import TrendFollowingStrategy

    class FakeMarketDataService:
        def __init__(self, candles_by_symbol):
            self.candles_by_symbol = candles_by_symbol

        def get_recent_candles(self, adapter_name, symbol, timeframe, limit):
            return self.candles_by_symbol[symbol]

    flat_then_breakout = _candles(
        "FLATUP/KRW",
        [100.0 + i * 0.04 for i in range(24)] + [101.2, 101.5, 101.8, 102.2, 102.2, 102.8],
        [1000.0] * 29 + [1500.0],
    )
    flat_then_breakout[-1].low = 102.0
    flat_then_breakout[-1].high = 102.85
    flat_then_breakout[-1].open = 102.1
    selector = DynamicSymbolSelector(
        market_data_service=FakeMarketDataService({"FLATUP/KRW": flat_then_breakout})
    )
    strategy = TrendFollowingStrategy()

    assert strategy.generate_signal(flat_then_breakout).action == "buy"
    assert selector._has_positive_short_momentum(flat_then_breakout)
    assert selector.select(["FLATUP/KRW"], timeframe="5m", top_n=1) == ["FLATUP/KRW"]


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
    clean_continuation[-1].high = 103.46
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


def test_selector_tighter_close_location_skips_soft_close_reversal():
    class FakeMarketDataService:
        def __init__(self, candles_by_symbol):
            self.candles_by_symbol = candles_by_symbol

        def get_recent_candles(self, adapter_name, symbol, timeframe, limit):
            return self.candles_by_symbol[symbol]

    soft_close = _candles(
        "SOFT/KRW",
        [100.0 + i * 0.08 for i in range(24)] + [102.0, 102.4, 102.8, 103.2, 103.8, 104.9],
        [1000.0] * 29 + [2600.0],
    )
    soft_close[-1].low = 103.0
    soft_close[-1].high = 105.2891566265
    soft_close[-1].open = 103.5
    clean_continuation = _candles(
        "CLEAN/KRW",
        [100.0 + i * 0.06 for i in range(24)] + [101.5, 101.8, 102.1, 102.5, 102.9, 103.5],
        [1000.0] * 29 + [1500.0],
    )
    clean_continuation[-1].low = 103.0
    clean_continuation[-1].high = 103.55
    clean_continuation[-1].open = 103.1
    selector = DynamicSymbolSelector(
        market_data_service=FakeMarketDataService(
            {
                "SOFT/KRW": soft_close,
                "CLEAN/KRW": clean_continuation,
            }
        )
    )

    soft_return_after_costs = ((102.8 * 0.9995) - (104.9 * 1.0005)) / (104.9 * 1.0005)
    clean_return_after_costs = ((105.9 * 0.9995) - (103.5 * 1.0005)) / (103.5 * 1.0005)

    assert selector._score(soft_close) > selector._score(clean_continuation)
    assert selector._has_positive_short_momentum(soft_close)
    assert selector._has_confirming_volume(soft_close)
    assert round((soft_close[-1].close - soft_close[-1].low) / (soft_close[-1].high - soft_close[-1].low), 2) == 0.83
    assert not selector._has_breakout_close_location(soft_close)
    assert selector._has_breakout_close_location(clean_continuation)
    assert soft_return_after_costs < 0
    assert clean_return_after_costs > 0
    assert selector.select(["SOFT/KRW", "CLEAN/KRW"], timeframe="5m", top_n=1) == ["CLEAN/KRW"]


def test_selector_close_location_matches_trend_entry_gate():
    class FakeMarketDataService:
        def __init__(self, candles_by_symbol):
            self.candles_by_symbol = candles_by_symbol

        def get_recent_candles(self, adapter_name, symbol, timeframe, limit):
            return self.candles_by_symbol[symbol]

    soft_close = _candles(
        "SOFT/KRW",
        [100.0 + i * 0.03 for i in range(24)] + [101.2, 101.5, 101.8, 102.1, 102.4, 103.0],
        [1000.0] * 29 + [1700.0],
    )
    soft_close[-1].low = 102.0
    soft_close[-1].high = 103.1628
    soft_close[-1].open = 102.25
    clean_continuation = _candles(
        "CLEAN/KRW",
        [100.0 + i * 0.035 for i in range(24)] + [101.3, 101.6, 101.9, 102.15, 102.45, 102.8],
        [1000.0] * 29 + [1550.0],
    )
    clean_continuation[-1].low = 102.0
    clean_continuation[-1].high = 102.8889
    clean_continuation[-1].open = 102.25
    market_data_service = FakeMarketDataService(
        {
            "SOFT/KRW": soft_close,
            "CLEAN/KRW": clean_continuation,
        }
    )
    baseline_selector = DynamicSymbolSelector(
        market_data_service=market_data_service,
        min_breakout_close_location=0.85,
    )
    candidate_selector = DynamicSymbolSelector(market_data_service=market_data_service)

    soft_return_after_costs = ((102.0 * 0.9995) - (103.0 * 1.0005)) / (103.0 * 1.0005)
    clean_return_after_costs = ((104.8 * 0.9995) - (102.8 * 1.0005)) / (102.8 * 1.0005)

    assert baseline_selector._score(soft_close) > baseline_selector._score(clean_continuation)
    assert round((soft_close[-1].close - soft_close[-1].low) / (soft_close[-1].high - soft_close[-1].low), 2) == 0.86
    assert baseline_selector._has_breakout_close_location(soft_close)
    assert candidate_selector._has_breakout_close_location(soft_close)
    assert candidate_selector._has_breakout_close_location(clean_continuation)
    assert soft_return_after_costs < 0
    assert clean_return_after_costs > 0
    assert baseline_selector.select(["SOFT/KRW", "CLEAN/KRW"], timeframe="5m", top_n=1) == ["SOFT/KRW"]
    assert candidate_selector.select(["SOFT/KRW", "CLEAN/KRW"], timeframe="5m", top_n=1) == ["SOFT/KRW"]


def test_selector_close_location_allows_strategy_strong_impulse_exception():
    from investment_bot.strategies.trend_following import TrendFollowingStrategy

    class FakeMarketDataService:
        def __init__(self, candles_by_symbol):
            self.candles_by_symbol = candles_by_symbol

        def get_recent_candles(self, adapter_name, symbol, timeframe, limit):
            return self.candles_by_symbol[symbol]

    strong_impulse = _candles(
        "IMPULSE/KRW",
        [100.0 + i * 0.04 for i in range(24)] + [101.2, 101.5, 101.9, 102.3, 102.8, 103.05],
        [1000.0] * 29 + [1850.0],
    )
    strong_impulse[-1].low = 102.2
    strong_impulse[-1].high = 103.2
    strong_impulse[-1].open = 102.35
    clean_continuation = _candles(
        "CLEAN/KRW",
        [100.0 + i * 0.035 for i in range(24)] + [101.2, 101.5, 101.8, 102.1, 102.4, 102.8],
        [1000.0] * 29 + [1500.0],
    )
    clean_continuation[-1].low = 102.0
    clean_continuation[-1].high = 102.8889
    clean_continuation[-1].open = 102.25
    market_data_service = FakeMarketDataService(
        {
            "IMPULSE/KRW": strong_impulse,
            "CLEAN/KRW": clean_continuation,
        }
    )
    old_selector = DynamicSymbolSelector(
        market_data_service=market_data_service,
        strong_breakout_close_location=0.88,
    )
    selector = DynamicSymbolSelector(market_data_service=market_data_service)
    strategy = TrendFollowingStrategy()

    assert round((strong_impulse[-1].close - strong_impulse[-1].low) / (strong_impulse[-1].high - strong_impulse[-1].low), 2) == 0.85
    assert strategy.generate_signal(strong_impulse).action == "buy"
    assert not old_selector._has_breakout_close_location(strong_impulse)
    assert selector._has_breakout_close_location(strong_impulse)
    assert selector._score(strong_impulse) > selector._score(clean_continuation)
    assert old_selector.select(["IMPULSE/KRW", "CLEAN/KRW"], timeframe="5m", top_n=1) == ["CLEAN/KRW"]
    assert selector.select(["IMPULSE/KRW", "CLEAN/KRW"], timeframe="5m", top_n=1) == ["IMPULSE/KRW"]


def test_selector_strong_impulse_volume_matches_trend_entry_gate():
    from investment_bot.strategies.trend_following import TrendFollowingStrategy

    class FakeMarketDataService:
        def __init__(self, candles_by_symbol):
            self.candles_by_symbol = candles_by_symbol

        def get_recent_candles(self, adapter_name, symbol, timeframe, limit):
            return self.candles_by_symbol[symbol]

    strong_impulse = _candles(
        "IMPULSE/KRW",
        [100.0 + i * 0.05 for i in range(24)] + [101.4, 101.8, 102.2, 102.7, 103.2, 103.45],
        [1000.0] * 29 + [1720.0],
    )
    strong_impulse[-1].low = 102.0
    strong_impulse[-1].high = 103.7059
    strong_impulse[-1].open = 102.4
    clean_continuation = _candles(
        "CLEAN/KRW",
        [100.0 + i * 0.045 for i in range(24)] + [101.2, 101.5, 101.8, 102.1, 102.45, 102.9],
        [1000.0] * 29 + [1500.0],
    )
    clean_continuation[-1].low = 102.3
    clean_continuation[-1].high = 102.975
    clean_continuation[-1].open = 102.5
    market_data_service = FakeMarketDataService(
        {
            "IMPULSE/KRW": strong_impulse,
            "CLEAN/KRW": clean_continuation,
        }
    )
    old_selector = DynamicSymbolSelector(
        market_data_service=market_data_service,
        strong_breakout_volume_surge=1.80,
    )
    selector = DynamicSymbolSelector(market_data_service=market_data_service)
    strategy = TrendFollowingStrategy()

    assert strategy.generate_signal(strong_impulse).action == "buy"
    assert round(selector._volume_surge(strong_impulse), 2) == 1.72
    assert not old_selector._has_breakout_close_location(strong_impulse)
    assert selector._has_breakout_close_location(strong_impulse)
    assert selector._has_breakout_close_location(clean_continuation)
    assert old_selector.select(["IMPULSE/KRW", "CLEAN/KRW"], timeframe="5m", top_n=1) == ["CLEAN/KRW"]
    assert selector.select(["IMPULSE/KRW", "CLEAN/KRW"], timeframe="5m", top_n=1) == ["IMPULSE/KRW"]


def test_selector_strong_impulse_volume_1p60_matches_trend_entry_gate():
    from investment_bot.strategies.trend_following import TrendFollowingStrategy

    class FakeMarketDataService:
        def __init__(self, candles_by_symbol):
            self.candles_by_symbol = candles_by_symbol

        def get_recent_candles(self, adapter_name, symbol, timeframe, limit):
            return self.candles_by_symbol[symbol]

    strong_impulse = _candles(
        "IMPULSE/KRW",
        [100.0 + i * 0.05 for i in range(24)] + [101.4, 101.8, 102.2, 102.7, 103.2, 103.45],
        [1000.0] * 29 + [1620.0],
    )
    strong_impulse[-1].low = 102.0
    strong_impulse[-1].high = 103.7059
    strong_impulse[-1].open = 102.4
    clean_continuation = _candles(
        "CLEAN/KRW",
        [100.0 + i * 0.045 for i in range(24)] + [101.2, 101.5, 101.8, 102.1, 102.45, 102.9],
        [1000.0] * 29 + [1500.0],
    )
    clean_continuation[-1].low = 102.3
    clean_continuation[-1].high = 102.975
    clean_continuation[-1].open = 102.5
    market_data_service = FakeMarketDataService(
        {
            "IMPULSE/KRW": strong_impulse,
            "CLEAN/KRW": clean_continuation,
        }
    )
    old_selector = DynamicSymbolSelector(
        market_data_service=market_data_service,
        strong_breakout_volume_surge=1.70,
    )
    selector = DynamicSymbolSelector(market_data_service=market_data_service)
    strategy = TrendFollowingStrategy()

    assert strategy.generate_signal(strong_impulse).action == "buy"
    assert round(selector._volume_surge(strong_impulse), 2) == 1.62
    assert not old_selector._has_breakout_close_location(strong_impulse)
    assert selector._has_breakout_close_location(strong_impulse)
    assert selector._has_breakout_close_location(clean_continuation)
    assert old_selector.select(["IMPULSE/KRW", "CLEAN/KRW"], timeframe="5m", top_n=1) == ["CLEAN/KRW"]
    assert selector.select(["IMPULSE/KRW", "CLEAN/KRW"], timeframe="5m", top_n=1) == ["IMPULSE/KRW"]


def test_selector_body_confirmation_matches_trend_entry_gate():
    from investment_bot.strategies.trend_following import TrendFollowingStrategy

    class FakeMarketDataService:
        def __init__(self, candles_by_symbol):
            self.candles_by_symbol = candles_by_symbol

        def get_recent_candles(self, adapter_name, symbol, timeframe, limit):
            return self.candles_by_symbol[symbol]

    class OldBodyAgnosticSelector(DynamicSymbolSelector):
        def _has_entry_green_body(self, candles):
            return True

    red_body_breakout = _candles(
        "RED/KRW",
        [100.0 + i * 0.055 for i in range(24)] + [101.5, 101.9, 102.3, 102.8, 103.4, 104.7],
        [1000.0] * 29 + [2100.0],
    )
    red_body_breakout[-1].low = 103.7
    red_body_breakout[-1].high = 104.8
    red_body_breakout[-1].open = 104.78
    clean_continuation = _candles(
        "CLEAN/KRW",
        [100.0 + i * 0.045 for i in range(24)] + [101.3, 101.65, 102.0, 102.35, 102.75, 103.2],
        [1000.0] * 29 + [1500.0],
    )
    clean_continuation[-1].low = 102.6
    clean_continuation[-1].high = 103.25
    clean_continuation[-1].open = 102.8
    market_data_service = FakeMarketDataService(
        {
            "RED/KRW": red_body_breakout,
            "CLEAN/KRW": clean_continuation,
        }
    )
    old_selector = OldBodyAgnosticSelector(market_data_service=market_data_service)
    selector = DynamicSymbolSelector(market_data_service=market_data_service)
    strategy = TrendFollowingStrategy()

    red_return_after_costs = ((103.0 * 0.9995) - (104.7 * 1.0005)) / (104.7 * 1.0005)
    clean_return_after_costs = ((105.4 * 0.9995) - (103.2 * 1.0005)) / (103.2 * 1.0005)

    assert strategy.generate_signal(red_body_breakout).action == "hold"
    assert strategy.generate_signal(clean_continuation).action == "buy"
    assert selector._score(red_body_breakout) > selector._score(clean_continuation)
    assert selector._has_breakout_close_location(red_body_breakout)
    assert not selector._has_entry_green_body(red_body_breakout)
    assert selector._has_entry_green_body(clean_continuation)
    assert red_return_after_costs < 0
    assert clean_return_after_costs > 0
    assert old_selector.select(["RED/KRW", "CLEAN/KRW"], timeframe="5m", top_n=1) == ["RED/KRW"]
    assert selector.select(["RED/KRW", "CLEAN/KRW"], timeframe="5m", top_n=1) == ["CLEAN/KRW"]


def test_selector_trend_gap_matches_trend_entry_gate():
    from investment_bot.strategies.trend_following import TrendFollowingStrategy

    class FakeMarketDataService:
        def __init__(self, candles_by_symbol):
            self.candles_by_symbol = candles_by_symbol

        def get_recent_candles(self, adapter_name, symbol, timeframe, limit):
            return self.candles_by_symbol[symbol]

    class OldTrendGapAgnosticSelector(DynamicSymbolSelector):
        def _has_breakout_trend_gap(self, candles):
            return True

    low_gap_breakout = _candles(
        "LOWGAP/KRW",
        [100.0] * 22 + [102.0, 102.0, 102.0, 102.0, 102.0, 102.02, 102.04, 102.12],
        [1000.0] * 29 + [3000.0],
    )
    actionable_breakout = _candles(
        "ACTION/KRW",
        [100.0 + i * 0.04 for i in range(24)] + [101.1, 101.3, 101.55, 101.8, 102.05, 102.35],
        [1000.0] * 29 + [1400.0],
    )
    for candles in (low_gap_breakout, actionable_breakout):
        candles[-1].low = candles[-1].close - 0.9
        candles[-1].high = candles[-1].close + 0.1
        candles[-1].open = candles[-1].close - 0.2

    market_data_service = FakeMarketDataService(
        {
            "LOWGAP/KRW": low_gap_breakout,
            "ACTION/KRW": actionable_breakout,
        }
    )
    old_selector = OldTrendGapAgnosticSelector(market_data_service=market_data_service)
    selector = DynamicSymbolSelector(market_data_service=market_data_service)
    strategy = TrendFollowingStrategy()

    low_gap_return_after_costs = ((101.5 * 0.9995) - (102.12 * 1.0005)) / (102.12 * 1.0005)
    actionable_return_after_costs = ((104.0 * 0.9995) - (102.35 * 1.0005)) / (102.35 * 1.0005)

    assert strategy.generate_signal(low_gap_breakout).action == "hold"
    assert strategy.generate_signal(actionable_breakout).action == "buy"
    assert old_selector._score(low_gap_breakout) > old_selector._score(actionable_breakout)
    assert not selector._has_breakout_trend_gap(low_gap_breakout)
    assert selector._has_breakout_trend_gap(actionable_breakout)
    assert low_gap_return_after_costs < 0
    assert actionable_return_after_costs > 0
    assert old_selector.select(["LOWGAP/KRW", "ACTION/KRW"], timeframe="5m", top_n=1) == ["LOWGAP/KRW"]
    assert selector.select(["LOWGAP/KRW", "ACTION/KRW"], timeframe="5m", top_n=1) == ["ACTION/KRW"]


def test_selector_rejects_overextended_trigger_candle():
    class FakeMarketDataService:
        def __init__(self, candles_by_symbol):
            self.candles_by_symbol = candles_by_symbol

        def get_recent_candles(self, adapter_name, symbol, timeframe, limit):
            return self.candles_by_symbol[symbol]

    overextended = _candles(
        "OVER/KRW",
        [100.0 + i * 0.05 for i in range(24)] + [101.4, 101.7, 102.0, 102.4, 102.8, 106.8],
        [1000.0] * 29 + [2600.0],
    )
    steady_continuation = _candles(
        "STEADY/KRW",
        [100.0 + i * 0.06 for i in range(24)] + [101.5, 101.8, 102.1, 102.4, 102.8, 104.0],
        [1000.0] * 29 + [1600.0],
    )
    selector = DynamicSymbolSelector(
        market_data_service=FakeMarketDataService(
            {
                "OVER/KRW": overextended,
                "STEADY/KRW": steady_continuation,
            }
        )
    )

    over_return_after_costs = ((104.2 * 0.9995) - (106.8 * 1.0005)) / (106.8 * 1.0005)
    steady_return_after_costs = ((106.0 * 0.9995) - (104.0 * 1.0005)) / (104.0 * 1.0005)

    assert selector._score(overextended) > selector._score(steady_continuation)
    assert selector._has_positive_short_momentum(overextended)
    assert selector._has_confirming_volume(overextended)
    assert selector._has_breakout_close_location(overextended)
    assert not selector._has_controlled_breakout_momentum(overextended)
    assert over_return_after_costs < 0
    assert steady_return_after_costs > 0
    assert selector.select(["OVER/KRW", "STEADY/KRW"], timeframe="5m", top_n=1) == ["STEADY/KRW"]


def test_selector_tighter_breakout_momentum_skips_late_single_bar_reversal():
    class FakeMarketDataService:
        def __init__(self, candles_by_symbol):
            self.candles_by_symbol = candles_by_symbol

        def get_recent_candles(self, adapter_name, symbol, timeframe, limit):
            return self.candles_by_symbol[symbol]

    late_spike = _candles(
        "LATE/KRW",
        [100.0 + i * 0.05 for i in range(25)] + [102.8, 103.0, 103.2, 103.5, 106.8],
        [1000.0] * 29 + [2600.0],
    )
    steady_continuation = _candles(
        "STEADY/KRW",
        [100.0 + i * 0.06 for i in range(25)] + [101.6, 102.0, 102.4, 102.8, 104.0],
        [1000.0] * 29 + [1700.0],
    )
    market_data_service = FakeMarketDataService(
        {
            "LATE/KRW": late_spike,
            "STEADY/KRW": steady_continuation,
        }
    )
    baseline_selector = DynamicSymbolSelector(
        market_data_service=market_data_service,
        max_breakout_momentum_pct=0.035,
        max_recent_breakout_runup_pct=0.05,
    )
    candidate_selector = DynamicSymbolSelector(
        market_data_service=market_data_service,
        max_recent_breakout_runup_pct=0.05,
    )

    late_return_after_costs = ((104.1 * 0.9995) - (106.8 * 1.0005)) / (106.8 * 1.0005)
    steady_return_after_costs = ((106.5 * 0.9995) - (104.0 * 1.0005)) / (104.0 * 1.0005)

    assert baseline_selector._score(late_spike) > baseline_selector._score(steady_continuation)
    assert baseline_selector._has_controlled_breakout_momentum(late_spike)
    assert not candidate_selector._has_controlled_breakout_momentum(late_spike)
    assert candidate_selector._has_controlled_breakout_momentum(steady_continuation)
    assert late_return_after_costs < 0
    assert steady_return_after_costs > 0
    assert baseline_selector.select(["LATE/KRW", "STEADY/KRW"], timeframe="5m", top_n=1) == ["LATE/KRW"]
    assert candidate_selector.select(["LATE/KRW", "STEADY/KRW"], timeframe="5m", top_n=1) == ["STEADY/KRW"]


def test_selector_rejects_overextended_recent_breakout_runup():
    class FakeMarketDataService:
        def __init__(self, candles_by_symbol):
            self.candles_by_symbol = candles_by_symbol

        def get_recent_candles(self, adapter_name, symbol, timeframe, limit):
            return self.candles_by_symbol[symbol]

    late_staircase = _candles(
        "LATE/KRW",
        [100.0 + i * 0.04 for i in range(25)] + [101.4, 102.6, 104.0, 105.2, 106.6],
        [1000.0] * 29 + [2400.0],
    )
    steady_continuation = _candles(
        "STEADY/KRW",
        [100.0 + i * 0.05 for i in range(25)] + [101.4, 101.8, 102.2, 102.7, 103.3],
        [1000.0] * 29 + [1500.0],
    )
    selector = DynamicSymbolSelector(
        market_data_service=FakeMarketDataService(
            {
                "LATE/KRW": late_staircase,
                "STEADY/KRW": steady_continuation,
            }
        )
    )

    late_return_after_costs = ((103.8 * 0.9995) - (106.6 * 1.0005)) / (106.6 * 1.0005)
    steady_return_after_costs = ((105.9 * 0.9995) - (103.3 * 1.0005)) / (103.3 * 1.0005)

    assert selector._score(late_staircase) > selector._score(steady_continuation)
    assert selector._has_positive_short_momentum(late_staircase)
    assert selector._has_confirming_volume(late_staircase)
    assert selector._has_breakout_close_location(late_staircase)
    assert selector._has_controlled_breakout_momentum(late_staircase)
    assert not selector._has_controlled_recent_runup(late_staircase)
    assert late_return_after_costs < 0
    assert steady_return_after_costs > 0
    assert selector.select(["LATE/KRW", "STEADY/KRW"], timeframe="5m", top_n=1) == ["STEADY/KRW"]


def test_selector_tighter_recent_runup_skips_exhausted_staircase():
    class FakeMarketDataService:
        def __init__(self, candles_by_symbol):
            self.candles_by_symbol = candles_by_symbol

        def get_recent_candles(self, adapter_name, symbol, timeframe, limit):
            return self.candles_by_symbol[symbol]

    exhausted_staircase = _candles(
        "EXHAUST/KRW",
        [100.0 + i * 0.03 for i in range(25)] + [101.6, 102.6, 103.7, 104.8, 106.3],
        [1000.0] * 29 + [2200.0],
    )
    steady_continuation = _candles(
        "STEADY/KRW",
        [100.0 + i * 0.05 for i in range(25)] + [101.4, 101.8, 102.3, 102.8, 103.4],
        [1000.0] * 29 + [1600.0],
    )
    baseline_selector = DynamicSymbolSelector(
        market_data_service=FakeMarketDataService(
            {
                "EXHAUST/KRW": exhausted_staircase,
                "STEADY/KRW": steady_continuation,
            }
        ),
        max_recent_breakout_runup_pct=0.05,
    )
    candidate_selector = DynamicSymbolSelector(
        market_data_service=FakeMarketDataService(
            {
                "EXHAUST/KRW": exhausted_staircase,
                "STEADY/KRW": steady_continuation,
            }
        )
    )

    exhaust_return_after_costs = ((104.3 * 0.9995) - (106.3 * 1.0005)) / (106.3 * 1.0005)
    steady_return_after_costs = ((105.8 * 0.9995) - (103.4 * 1.0005)) / (103.4 * 1.0005)

    assert baseline_selector._score(exhausted_staircase) > baseline_selector._score(steady_continuation)
    assert baseline_selector._has_controlled_recent_runup(exhausted_staircase)
    assert not candidate_selector._has_controlled_recent_runup(exhausted_staircase)
    assert candidate_selector._has_controlled_recent_runup(steady_continuation)
    assert exhaust_return_after_costs < 0
    assert steady_return_after_costs > 0
    assert baseline_selector.select(["EXHAUST/KRW", "STEADY/KRW"], timeframe="5m", top_n=1) == ["EXHAUST/KRW"]
    assert candidate_selector.select(["EXHAUST/KRW", "STEADY/KRW"], timeframe="5m", top_n=1) == ["STEADY/KRW"]


def test_selector_tighter_3p5pct_recent_runup_skips_late_staircase_fade():
    class FakeMarketDataService:
        def __init__(self, candles_by_symbol):
            self.candles_by_symbol = candles_by_symbol

        def get_recent_candles(self, adapter_name, symbol, timeframe, limit):
            return self.candles_by_symbol[symbol]

    late_staircase = _candles(
        "LATE/KRW",
        [100.0 + i * 0.04 for i in range(25)] + [101.2, 101.9, 102.6, 103.4, 105.0],
        [1000.0] * 29 + [2100.0],
    )
    steady_continuation = _candles(
        "STEADY/KRW",
        [100.0 + i * 0.05 for i in range(25)] + [101.5, 101.9, 102.4, 102.9, 103.5],
        [1000.0] * 29 + [1550.0],
    )
    baseline_selector = DynamicSymbolSelector(
        market_data_service=FakeMarketDataService(
            {
                "LATE/KRW": late_staircase,
                "STEADY/KRW": steady_continuation,
            }
        ),
        max_recent_breakout_runup_pct=0.04,
    )
    candidate_selector = DynamicSymbolSelector(
        market_data_service=FakeMarketDataService(
            {
                "LATE/KRW": late_staircase,
                "STEADY/KRW": steady_continuation,
            }
        )
    )

    late_return_after_costs = ((103.6 * 0.9995) - (105.0 * 1.0005)) / (105.0 * 1.0005)
    steady_return_after_costs = ((105.9 * 0.9995) - (103.5 * 1.0005)) / (103.5 * 1.0005)

    assert baseline_selector._score(late_staircase) > baseline_selector._score(steady_continuation)
    assert baseline_selector._has_controlled_recent_runup(late_staircase)
    assert not candidate_selector._has_controlled_recent_runup(late_staircase)
    assert candidate_selector._has_controlled_recent_runup(steady_continuation)
    assert late_return_after_costs < 0
    assert steady_return_after_costs > 0
    assert baseline_selector.select(["LATE/KRW", "STEADY/KRW"], timeframe="5m", top_n=1) == ["LATE/KRW"]
    assert candidate_selector.select(["LATE/KRW", "STEADY/KRW"], timeframe="5m", top_n=1) == ["STEADY/KRW"]


def test_selector_tighter_3p3pct_recent_runup_skips_late_staircase_fade():
    class FakeMarketDataService:
        def __init__(self, candles_by_symbol):
            self.candles_by_symbol = candles_by_symbol

        def get_recent_candles(self, adapter_name, symbol, timeframe, limit):
            return self.candles_by_symbol[symbol]

    late_staircase = _candles(
        "LATE/KRW",
        [100.0 + i * 0.035 for i in range(25)] + [101.1, 101.8, 102.4, 103.0, 104.48],
        [1000.0] * 29 + [2050.0],
    )
    steady_continuation = _candles(
        "STEADY/KRW",
        [100.0 + i * 0.045 for i in range(25)] + [101.4, 101.8, 102.2, 102.7, 103.2],
        [1000.0] * 29 + [1550.0],
    )
    market_data_service = FakeMarketDataService(
        {
            "LATE/KRW": late_staircase,
            "STEADY/KRW": steady_continuation,
        }
    )
    baseline_selector = DynamicSymbolSelector(
        market_data_service=market_data_service,
        max_recent_breakout_runup_pct=0.034,
    )
    candidate_selector = DynamicSymbolSelector(market_data_service=market_data_service)

    late_return_after_costs = ((103.0 * 0.9995) - (104.48 * 1.0005)) / (104.48 * 1.0005)
    steady_return_after_costs = ((105.4 * 0.9995) - (103.2 * 1.0005)) / (103.2 * 1.0005)

    assert baseline_selector._score(late_staircase) > baseline_selector._score(steady_continuation)
    assert baseline_selector._has_controlled_recent_runup(late_staircase)
    assert not candidate_selector._has_controlled_recent_runup(late_staircase)
    assert candidate_selector._has_controlled_recent_runup(steady_continuation)
    assert late_return_after_costs < 0
    assert steady_return_after_costs > 0
    assert baseline_selector.select(["LATE/KRW", "STEADY/KRW"], timeframe="5m", top_n=1) == ["LATE/KRW"]
    assert candidate_selector.select(["LATE/KRW", "STEADY/KRW"], timeframe="5m", top_n=1) == ["STEADY/KRW"]


def test_selector_penalizes_noisy_wide_range_breakout_for_smoother_continuation():
    class FakeMarketDataService:
        def __init__(self, candles_by_symbol):
            self.candles_by_symbol = candles_by_symbol

        def get_recent_candles(self, adapter_name, symbol, timeframe, limit):
            return self.candles_by_symbol[symbol]

    noisy_breakout = _candles(
        "NOISY/KRW",
        [100.0 + i * 0.02 for i in range(20)] + [102.0, 101.0, 100.0, 99.0, 99.2, 99.4, 100.3, 101.2, 102.0, 102.6],
        [1000.0] * 29 + [1800.0],
    )
    smooth_continuation = _candles(
        "SMOOTH/KRW",
        [100.0 + i * 0.05 for i in range(24)] + [101.4, 101.7, 102.0, 102.3, 102.7, 103.0],
        [1000.0] * 29 + [1850.0],
    )
    selector = DynamicSymbolSelector(
        market_data_service=FakeMarketDataService(
            {
                "NOISY/KRW": noisy_breakout,
                "SMOOTH/KRW": smooth_continuation,
            }
        )
    )

    old_noisy_score = 0.108878 + 3.5087719298 + 18.0 + 2.8941176471
    old_smooth_score = 0.110495 + 1.9417475728 + 18.5 + 3.1460564752
    noisy_return_after_costs = ((101.2 * 0.9995) - (102.6 * 1.0005)) / (102.6 * 1.0005)
    smooth_return_after_costs = ((105.0 * 0.9995) - (103.0 * 1.0005)) / (103.0 * 1.0005)

    assert old_noisy_score > old_smooth_score
    assert selector._score(smooth_continuation) > selector._score(noisy_breakout)
    assert noisy_return_after_costs < 0
    assert smooth_return_after_costs > 0
    assert selector.select(["NOISY/KRW", "SMOOTH/KRW"], timeframe="5m", top_n=1) == ["SMOOTH/KRW"]
