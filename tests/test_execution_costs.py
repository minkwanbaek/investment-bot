from investment_bot.services.paper_broker import PaperBroker


def test_paper_broker_applies_fee_and_slippage_to_buy_orders():
    broker = PaperBroker(starting_cash=1000, trading_fee_pct=0.1, slippage_pct=0.1)

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

    order = result["order"]
    assert order["requested_price"] == 100
    assert order["execution_price"] == 100.1
    assert order["fee_paid"] == 0.1001
    assert broker.cash_balance == 899.7999


def test_paper_broker_applies_fee_and_slippage_to_sell_orders():
    broker = PaperBroker(starting_cash=1000, trading_fee_pct=0.1, slippage_pct=0.1)
    broker.submit(
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

    result = broker.submit(
        {
            "strategy_name": "trend_following",
            "symbol": "BTC/KRW",
            "action": "sell",
            "confidence": 0.5,
            "size_scale": 0.5,
            "reason": "sell",
        },
        execution_price=120,
    )

    order = result["order"]
    assert order["execution_price"] == 119.88
    assert order["fee_paid"] == 0.0599
    assert broker.total_realized_pnl > 0
