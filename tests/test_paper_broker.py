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


def test_paper_broker_preserves_small_crypto_quantities():
    broker = PaperBroker(starting_cash=500000, trading_fee_pct=0.0, slippage_pct=0.0, min_order_notional=0.0)

    broker.submit(
        {
            "strategy_name": "trend_following",
            "symbol": "BTC/KRW",
            "action": "buy",
            "confidence": 0.2,
            "size_scale": 0.00060394,
            "reason": "small live-like buy",
        },
        execution_price=104500000,
    )

    snapshot = broker.portfolio_snapshot()
    position = snapshot["positions"]["BTC/KRW"]

    assert position["quantity"] == 0.00060394
    assert position["cost_basis"] > 0
    assert position["market_value"] > 0


def test_paper_broker_symbol_exposure_limit_uses_current_equity_after_profit():
    broker = PaperBroker(
        starting_cash=10000,
        trading_fee_pct=0.0,
        slippage_pct=0.0,
        min_order_notional=0.0,
        max_symbol_exposure_pct=10.0,
    )

    assert broker.submit(
        {
            "strategy_name": "trend_following",
            "symbol": "BTC/KRW",
            "action": "buy",
            "confidence": 1.0,
            "size_scale": 10.0,
            "reason": "initial cap-sized buy",
        },
        execution_price=100,
    )["status"] == "recorded"
    assert broker.submit(
        {
            "strategy_name": "trend_following",
            "symbol": "BTC/KRW",
            "action": "sell",
            "confidence": 1.0,
            "size_scale": 10.0,
            "reason": "realize profit",
        },
        execution_price=120,
    )["status"] == "recorded"

    follow_on = broker.submit(
        {
            "strategy_name": "trend_following",
            "symbol": "BTC/KRW",
            "action": "buy",
            "confidence": 1.0,
            "size_scale": 10.1,
            "reason": "compound after realized profit",
        },
        execution_price=100,
    )

    assert broker.cash_balance == 9190.0
    assert follow_on["status"] == "recorded"
    assert broker.portfolio_snapshot()["positions"]["BTC/KRW"]["market_value"] == 1010.0
