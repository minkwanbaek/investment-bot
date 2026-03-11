from investment_bot.services.paper_broker import PaperBroker


def test_broker_rejects_buy_below_min_order_notional():
    broker = PaperBroker(starting_cash=10000, min_order_notional=5000, trading_fee_pct=0.0, slippage_pct=0.0, max_symbol_exposure_pct=100)
    result = broker.submit(
        {
            "strategy_name": "trend_following",
            "symbol": "BTC/KRW",
            "action": "buy",
            "confidence": 0.1,
            "size_scale": 1.0,
            "reason": "buy",
        },
        execution_price=100,
    )
    assert result["status"] == "rejected"
    assert result["reason"] == "below_min_order_notional"


def test_broker_rejects_buy_when_cash_is_insufficient():
    broker = PaperBroker(starting_cash=50, min_order_notional=1, trading_fee_pct=0.0, slippage_pct=0.0, max_symbol_exposure_pct=100)
    result = broker.submit(
        {
            "strategy_name": "trend_following",
            "symbol": "BTC/KRW",
            "action": "buy",
            "confidence": 1.0,
            "size_scale": 1.0,
            "reason": "buy",
        },
        execution_price=100,
    )
    assert result["status"] == "rejected"
    assert result["reason"] == "insufficient_cash"


def test_broker_rejects_when_max_consecutive_buys_is_reached():
    broker = PaperBroker(starting_cash=10000, min_order_notional=1, trading_fee_pct=0.0, slippage_pct=0.0, max_consecutive_buys=1, max_symbol_exposure_pct=100)
    first = broker.submit(
        {
            "strategy_name": "trend_following",
            "symbol": "BTC/KRW",
            "action": "buy",
            "confidence": 1.0,
            "size_scale": 1.0,
            "reason": "buy",
        },
        execution_price=100,
    )
    second = broker.submit(
        {
            "strategy_name": "trend_following",
            "symbol": "BTC/KRW",
            "action": "buy",
            "confidence": 1.0,
            "size_scale": 1.0,
            "reason": "buy-again",
        },
        execution_price=100,
    )
    assert first["status"] == "recorded"
    assert second["status"] == "rejected"
    assert second["reason"] == "max_consecutive_buys_reached"
