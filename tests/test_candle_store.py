from investment_bot.models.market import Candle
from investment_bot.services.candle_store import CandleStore


def test_candle_store_appends_and_reads_recent_candles(tmp_path):
    store = CandleStore(str(tmp_path / "candles.json"))
    candles = [
        Candle(symbol="BTC/KRW", timeframe="1h", open=1, high=1, low=1, close=close, volume=1, timestamp=str(i))
        for i, close in enumerate([100, 101, 102], start=1)
    ]

    store.append(symbol="BTC/KRW", timeframe="1h", candles=candles)
    recent = store.list_recent(symbol="BTC/KRW", timeframe="1h", limit=2)

    assert [item.close for item in recent] == [101, 102]


def test_candle_store_deduplicates_by_timestamp(tmp_path):
    store = CandleStore(str(tmp_path / "candles.json"))
    store.append(
        symbol="BTC/KRW",
        timeframe="1h",
        candles=[Candle(symbol="BTC/KRW", timeframe="1h", open=1, high=1, low=1, close=100, volume=1, timestamp="1")],
    )
    store.append(
        symbol="BTC/KRW",
        timeframe="1h",
        candles=[Candle(symbol="BTC/KRW", timeframe="1h", open=1, high=1, low=1, close=105, volume=1, timestamp="1")],
    )

    recent = store.list_recent(symbol="BTC/KRW", timeframe="1h", limit=5)
    assert len(recent) == 1
    assert recent[0].close == 105
