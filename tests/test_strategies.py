from investment_bot.models.market import Candle
from investment_bot.strategies.dca import DCAStrategy
from investment_bot.strategies.mean_reversion import MeanReversionStrategy
from investment_bot.strategies.trend_following import TrendFollowingStrategy


def test_trend_following_returns_signal():
    candles = [
        Candle(symbol="BTC/KRW", timeframe="1h", open=1, high=1, low=1, close=c, volume=1, timestamp=str(i))
        for i, c in enumerate([100, 101, 102, 103, 104, 105, 106, 107])
    ]
    signal = TrendFollowingStrategy().generate_signal(candles)
    assert signal.symbol == "BTC/KRW"
    assert signal.action in {"buy", "sell", "hold"}


def test_trend_following_holds_on_small_noisy_gap():
    candles = [
        Candle(symbol="BTC/KRW", timeframe="1h", open=1, high=1, low=1, close=c, volume=1, timestamp=str(i))
        for i, c in enumerate([100, 100.05, 100.02, 100.07, 100.03, 100.08, 100.04, 100.09])
    ]
    signal = TrendFollowingStrategy().generate_signal(candles)
    assert signal.action == "hold"


def test_trend_following_buys_on_clear_uptrend_with_positive_momentum():
    candles = [
        Candle(symbol="BTC/KRW", timeframe="1h", open=1, high=1, low=1, close=close, volume=volume, timestamp=str(i))
        for i, (close, volume) in enumerate(
            zip([100, 101, 102, 103, 104, 105, 107, 109], [10, 10, 10, 10, 10, 10, 10, 15])
        )
    ]
    signal = TrendFollowingStrategy().generate_signal(candles)
    assert signal.action == "buy"


def test_trend_following_holds_low_volume_breakout():
    candles = [
        Candle(symbol="BTC/KRW", timeframe="1h", open=1, high=1, low=1, close=close, volume=volume, timestamp=str(i))
        for i, (close, volume) in enumerate(
            zip([100, 101, 102, 103, 104, 105, 107, 109], [10, 10, 10, 10, 10, 10, 10, 4])
        )
    ]
    signal = TrendFollowingStrategy().generate_signal(candles)
    assert signal.action == "hold"
    assert signal.meta["entry_volume_ratio"] == 0.4


def test_trend_following_holds_on_average_plus_volume_breakout_below_default_volume_gate():
    candles = [
        Candle(symbol="BTC/KRW", timeframe="1h", open=1, high=1, low=1, close=close, volume=volume, timestamp=str(i))
        for i, (close, volume) in enumerate(
            zip([100, 101, 102, 103, 104, 105, 107, 109], [10, 10, 10, 10, 10, 10, 10, 11])
        )
    ]
    signal = TrendFollowingStrategy().generate_signal(candles)
    assert signal.action == "hold"
    assert signal.meta["entry_volume_ratio"] == 1.1


def test_trend_following_holds_upper_wick_breakout():
    candles = [
        Candle(symbol="BTC/KRW", timeframe="1h", open=close, high=close, low=close, close=close, volume=10, timestamp=str(i))
        for i, close in enumerate([100, 101, 102, 103, 104, 105, 107])
    ]
    candles.append(
        Candle(
            symbol="BTC/KRW",
            timeframe="1h",
            open=107,
            high=116,
            low=106,
            close=109,
            volume=12,
            timestamp="7",
        )
    )
    signal = TrendFollowingStrategy().generate_signal(candles)
    assert signal.action == "hold"
    assert signal.meta["entry_close_location"] == 0.3


def test_trend_following_holds_marginal_close_location_breakout():
    candles = [
        Candle(symbol="BTC/KRW", timeframe="1h", open=close, high=close, low=close, close=close, volume=10, timestamp=str(i))
        for i, close in enumerate([100, 101, 102, 103, 104, 105, 107])
    ]
    candles.append(
        Candle(
            symbol="BTC/KRW",
            timeframe="1h",
            open=107,
            high=111,
            low=101,
            close=107.5,
            volume=13,
            timestamp="7",
        )
    )
    signal = TrendFollowingStrategy().generate_signal(candles)
    assert signal.action == "hold"
    assert signal.meta["entry_close_location"] == 0.65


def test_trend_following_holds_weak_close_location_breakout():
    candles = [
        Candle(symbol="BTC/KRW", timeframe="1h", open=close, high=close, low=close, close=close, volume=10, timestamp=str(i))
        for i, close in enumerate([100, 100.2, 100.5, 100.8, 101.0, 101.2, 101.4])
    ]
    candles.append(
        Candle(
            symbol="BTC/KRW",
            timeframe="1h",
            open=101.4,
            high=102.5,
            low=101.0714285714,
            close=102.1,
            volume=14,
            timestamp="7",
        )
    )
    signal = TrendFollowingStrategy().generate_signal(candles)
    assert signal.action == "hold"
    assert signal.meta["entry_close_location"] == 0.72


def test_trend_following_holds_red_body_breakout():
    candles = [
        Candle(symbol="BTC/KRW", timeframe="1h", open=close, high=close, low=close, close=close, volume=10, timestamp=str(i))
        for i, close in enumerate([100, 100.5, 101.0, 101.4, 101.8, 102.0, 102.3])
    ]
    candles.append(
        Candle(
            symbol="BTC/KRW",
            timeframe="1h",
            open=103.0,
            high=103.0,
            low=101.3,
            close=102.8,
            volume=15,
            timestamp="7",
        )
    )

    signal = TrendFollowingStrategy().generate_signal(candles)

    assert signal.action == "hold"
    assert signal.meta["entry_green_body_confirmed"] is False
    assert signal.meta["entry_close_location"] == 0.882353
    assert signal.meta["breakout_confirmed"] is True


def test_trend_following_holds_rebound_below_recent_high():
    candles = [
        Candle(symbol="BTC/KRW", timeframe="1h", open=close, high=close, low=close, close=close, volume=10, timestamp=str(i))
        for i, close in enumerate([100, 100, 100, 115, 105, 106, 107])
    ]
    candles.append(
        Candle(
            symbol="BTC/KRW",
            timeframe="1h",
            open=107,
            high=110,
            low=105,
            close=109,
            volume=16,
            timestamp="7",
        )
    )
    signal = TrendFollowingStrategy().generate_signal(candles)
    assert signal.action == "hold"
    assert signal.meta["breakout_confirmed"] is False
    assert signal.meta["recent_high_close"] == 115


def test_trend_following_sells_on_clear_downtrend_with_negative_momentum():
    candles = [
        Candle(symbol="BTC/KRW", timeframe="1h", open=1, high=1, low=1, close=c, volume=1, timestamp=str(i))
        for i, c in enumerate([109, 108, 107, 106, 105, 104, 103, 101])
    ]
    signal = TrendFollowingStrategy().generate_signal(candles)
    assert signal.action == "sell"


def test_trend_following_emits_exit_hints_for_open_position():
    candles = [
        Candle(symbol="BTC/KRW", timeframe="1h", open=close, high=close, low=close, close=close, volume=10, timestamp=str(i))
        for i, close in enumerate([100, 100.2, 100.4, 100.6, 100.8, 100.6, 100.2, 98.4])
    ]

    class Broker:
        positions = {
            "BTC/KRW": {
                "quantity": 1.0,
                "average_price": 100.0,
            }
        }

    signal = TrendFollowingStrategy().generate_signal(candles, broker=Broker())

    assert signal.action == "hold"
    assert signal.reason == "position_open_no_exit"
    assert signal.meta["strategy_stop_loss_pct"] == TrendFollowingStrategy.stop_loss_pct
    assert signal.meta["strategy_take_profit_pct"] == TrendFollowingStrategy.take_profit_pct
    assert signal.meta["trend_reversal_hint"] is True


def test_mean_reversion_buys_on_deep_discount_with_stabilizing_momentum():
    candles = [
        Candle(symbol="ETH/KRW", timeframe="1h", open=1, high=1, low=1, close=c, volume=1, timestamp=str(i))
        for i, c in enumerate([100, 101, 100, 99, 98, 95, 90, 94])
    ]
    signal = MeanReversionStrategy().generate_signal(candles)
    assert signal.action == "buy"
    assert signal.confidence == 0.50


def test_mean_reversion_waits_for_volume_confirmed_rebound():
    closes = [100, 101, 100, 99, 98, 95, 90, 94]
    volumes = [10, 10, 10, 10, 10, 10, 10, 4]
    candles = [
        Candle(symbol="ETH/KRW", timeframe="1h", open=1, high=1, low=1, close=close, volume=volume, timestamp=str(i))
        for i, (close, volume) in enumerate(zip(closes, volumes))
    ]
    signal = MeanReversionStrategy().generate_signal(candles)
    assert signal.action == "hold"
    assert signal.meta["buy_volume_ratio"] == 0.4


def test_mean_reversion_holds_without_clear_reversal_setup():
    candles = [
        Candle(symbol="ETH/KRW", timeframe="1h", open=1, high=1, low=1, close=c, volume=1, timestamp=str(i))
        for i, c in enumerate([100, 101, 100, 99, 98, 97, 96, 95])
    ]
    signal = MeanReversionStrategy().generate_signal(candles)
    assert signal.action == "hold"


def test_mean_reversion_emits_exit_hints_for_managed_position():
    candles = [
        Candle(symbol="ETH/KRW", timeframe="1h", open=1, high=1, low=1, close=c, volume=1, timestamp=str(i))
        for i, c in enumerate([98, 99, 99, 100, 100, 100, 100, 101.3])
    ]

    class Broker:
        positions = {
            "ETH/KRW": {
                "quantity": 2.0,
                "average_price": 100.0,
            }
        }

    signal = MeanReversionStrategy().generate_signal(candles, broker=Broker())
    assert signal.action == "hold"
    assert signal.reason == "position_open_no_exit"
    assert signal.meta["managed_rebound_exit_reason"] == "mean_reversion_managed_rebound_exit"
    assert signal.meta["managed_rebound_exit_threshold"] == MeanReversionStrategy.managed_rebound_exit_threshold


def test_dca_only_buys_on_meaningful_pullback():
    candles = [
        Candle(symbol="BTC/KRW", timeframe="1h", open=1, high=1, low=1, close=c, volume=1, timestamp=str(i))
        for i, c in enumerate([100, 101, 102, 103, 104, 105, 98, 99])
    ]
    signal = DCAStrategy().generate_signal(candles)
    assert signal.action == "buy"
    assert signal.confidence == 0.50


def test_dca_waits_for_rebound_on_falling_pullback():
    candles = [
        Candle(symbol="BTC/KRW", timeframe="1h", open=1, high=1, low=1, close=c, volume=1, timestamp=str(i))
        for i, c in enumerate([100, 101, 102, 103, 104, 105, 99, 98])
    ]
    signal = DCAStrategy().generate_signal(candles)
    assert signal.action == "hold"
    assert "momentum_pct=-" in signal.reason


def test_dca_skips_extreme_crash_drawdown():
    candles = [
        Candle(symbol="ONDO/KRW", timeframe="5m", open=1, high=1, low=1, close=c, volume=1, timestamp=str(i))
        for i, c in enumerate([100, 100, 100, 100, 100, 100, 91, 91])
    ]
    signal = DCAStrategy().generate_signal(candles)
    assert signal.action == "hold"
    assert "drawdown_pct=-0.0691" in signal.reason


def test_dca_holds_without_pullback():
    candles = [
        Candle(symbol="BTC/KRW", timeframe="1h", open=1, high=1, low=1, close=c, volume=1, timestamp=str(i))
        for i, c in enumerate([100, 101, 102, 103, 104, 105, 106, 107])
    ]
    signal = DCAStrategy().generate_signal(candles)
    assert signal.action == "hold"


def test_dca_emits_exit_hints_for_managed_position():
    candles = [
        Candle(symbol="BTC/KRW", timeframe="1h", open=1, high=1, low=1, close=c, volume=1, timestamp=str(i))
        for i, c in enumerate([98, 99, 99, 100, 100, 100, 100, 101.3])
    ]

    class Broker:
        positions = {
            "BTC/KRW": {
                "quantity": 2.0,
                "average_price": 100.0,
            }
        }

    signal = DCAStrategy().generate_signal(candles, broker=Broker())
    assert signal.action == "hold"
    assert signal.reason == "position_open_no_exit"
    assert signal.meta["managed_rebound_exit_reason"] == "value_dca_rebound_exit"
    assert signal.meta["managed_rebound_exit_threshold"] == DCAStrategy.sell_rebound_threshold
