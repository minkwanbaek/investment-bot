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
            zip([100, 101, 102, 103, 104, 105, 107, 109], [10, 10, 10, 10, 10, 10, 10, 13])
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


def test_trend_following_holds_average_volume_breakout():
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


def test_mean_reversion_buys_on_deep_discount_with_stabilizing_momentum():
    candles = [
        Candle(symbol="ETH/KRW", timeframe="1h", open=1, high=1, low=1, close=c, volume=1, timestamp=str(i))
        for i, c in enumerate([100, 101, 100, 99, 98, 95, 90, 94])
    ]
    signal = MeanReversionStrategy().generate_signal(candles)
    assert signal.action == "buy"


def test_mean_reversion_holds_without_clear_reversal_setup():
    candles = [
        Candle(symbol="ETH/KRW", timeframe="1h", open=1, high=1, low=1, close=c, volume=1, timestamp=str(i))
        for i, c in enumerate([100, 101, 100, 99, 98, 97, 96, 95])
    ]
    signal = MeanReversionStrategy().generate_signal(candles)
    assert signal.action == "hold"


def test_dca_only_buys_on_meaningful_pullback():
    candles = [
        Candle(symbol="BTC/KRW", timeframe="1h", open=1, high=1, low=1, close=c, volume=1, timestamp=str(i))
        for i, c in enumerate([100, 101, 102, 103, 104, 105, 98, 99])
    ]
    signal = DCAStrategy().generate_signal(candles)
    assert signal.action == "buy"


def test_dca_holds_without_pullback():
    candles = [
        Candle(symbol="BTC/KRW", timeframe="1h", open=1, high=1, low=1, close=c, volume=1, timestamp=str(i))
        for i, c in enumerate([100, 101, 102, 103, 104, 105, 106, 107])
    ]
    signal = DCAStrategy().generate_signal(candles)
    assert signal.action == "hold"
