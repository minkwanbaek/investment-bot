from investment_bot.models.market import Candle
from investment_bot.strategies.trend_following import TrendFollowingStrategy


def test_trend_following_returns_signal():
    candles = [
        Candle(symbol="BTC/KRW", timeframe="1h", open=1, high=1, low=1, close=c, volume=1, timestamp=str(i))
        for i, c in enumerate([100, 101, 102, 103, 104])
    ]
    signal = TrendFollowingStrategy().generate_signal(candles)
    assert signal.symbol == "BTC/KRW"
    assert signal.action in {"buy", "sell", "hold"}
