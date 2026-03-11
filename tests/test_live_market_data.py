from investment_bot.market_data.live import LiveMarketDataAdapter


def test_live_adapter_converts_symbol_to_upbit_market():
    adapter = LiveMarketDataAdapter()
    assert adapter._to_upbit_market("BTC/KRW") == "KRW-BTC"


def test_live_adapter_maps_supported_timeframes():
    adapter = LiveMarketDataAdapter()
    assert adapter._timeframe_to_minutes("1h") == 60
    assert adapter._timeframe_to_minutes("5m") == 5
