import httpx
import pytest

from investment_bot.market_data.live import LiveMarketDataAdapter


def test_live_adapter_converts_symbol_to_upbit_market():
    adapter = LiveMarketDataAdapter()
    assert adapter._to_upbit_market("BTC/KRW") == "KRW-BTC"


def test_live_adapter_maps_supported_timeframes():
    adapter = LiveMarketDataAdapter()
    assert adapter._timeframe_to_minutes("1h") == 60
    assert adapter._timeframe_to_minutes("5m") == 5


def test_live_adapter_retries_transient_fetch_error(monkeypatch):
    calls = {"count": 0}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return [
                {
                    "opening_price": 1,
                    "high_price": 2,
                    "low_price": 0.5,
                    "trade_price": 1.5,
                    "candle_acc_trade_volume": 10,
                    "candle_date_time_utc": "2026-01-01T00:00:00",
                }
            ]

    def fake_get(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise httpx.TimeoutException("timeout")
        return FakeResponse()

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr("investment_bot.market_data.live.time.sleep", lambda *_: None)

    adapter = LiveMarketDataAdapter(max_retries=2, retry_backoff_seconds=0.01)
    candles = adapter.get_recent_candles("BTC/KRW", "5m", 1)

    assert calls["count"] == 2
    assert len(candles) == 1
    assert candles[0].close == 1.5


def test_live_adapter_raises_after_retry_budget_exhausted(monkeypatch):
    calls = {"count": 0}

    def fake_get(*args, **kwargs):
        calls["count"] += 1
        raise httpx.TimeoutException("timeout")

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr("investment_bot.market_data.live.time.sleep", lambda *_: None)

    adapter = LiveMarketDataAdapter(max_retries=2, retry_backoff_seconds=0.01)

    with pytest.raises(httpx.TimeoutException):
        adapter.get_recent_candles("BTC/KRW", "5m", 1)

    assert calls["count"] == 3
