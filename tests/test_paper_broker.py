from investment_bot.services.paper_broker import PaperBroker


def test_paper_broker_tracks_average_price_and_unrealized_pnl():
    broker = PaperBroker(starting_cash=1000, trading_fee_pct=0.0, slippage_pct=0.0, min_order_notional=0.0)

    broker.submit(
        {
            "strategy_name": "trend_following",
            "symbol": "BTC/KRW",
            "action": "buy",
            "confidence": 0.5,
            "size_scale": 0.5,
            "reason": "first buy",
        },
        execution_price=100,
    )
    broker.submit(
        {
            "strategy_name": "trend_following",
            "symbol": "BTC/KRW",
            "action": "buy",
            "confidence": 0.5,
            "size_scale": 0.5,
            "reason": "second buy",
        },
        execution_price=200,
    )
    broker.mark_price("BTC/KRW", 150)

    snapshot = broker.portfolio_snapshot()
    position = snapshot["positions"]["BTC/KRW"]

    assert position["quantity"] == 1.0
    assert position["average_price"] == 150.0
    assert position["unrealized_pnl"] == 0.0
    assert snapshot["cash_balance"] == 850.0


def test_paper_broker_tracks_realized_pnl_on_sell():
    broker = PaperBroker(starting_cash=1000, trading_fee_pct=0.0, slippage_pct=0.0, min_order_notional=0.0)

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
    broker.submit(
        {
            "strategy_name": "trend_following",
            "symbol": "BTC/KRW",
            "action": "sell",
            "confidence": 0.4,
            "size_scale": 0.4,
            "reason": "partial sell",
        },
        execution_price=150,
    )

    snapshot = broker.portfolio_snapshot()
    position = snapshot["positions"]["BTC/KRW"]

    assert position["quantity"] == 0.6
    assert position["realized_pnl"] == 20.0
    assert snapshot["total_realized_pnl"] == 20.0
    assert snapshot["cash_balance"] == 960.0
