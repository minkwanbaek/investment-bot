from investment_bot.models.signal import TradeSignal
from investment_bot.risk.controller import RiskController
from investment_bot.services.paper_broker import PaperBroker


def test_risk_controller_sizes_from_cash_balance_and_price():
    controller = RiskController(max_confidence_position_scale=0.1)
    signal = TradeSignal(
        strategy_name="trend_following",
        symbol="BTC/KRW",
        action="buy",
        confidence=0.5,
        reason="trend",
    )

    review = controller.review(signal, cash_balance=10000, latest_price=100)

    assert review["target_notional"] == 500.0
    assert review["size_scale"] == 5.0


def test_risk_controller_floors_buy_to_min_order_notional_when_cash_allows():
    controller = RiskController(max_confidence_position_scale=0.01, min_order_notional=5000)
    signal = TradeSignal(
        strategy_name="trend_following",
        symbol="BTC/KRW",
        action="buy",
        confidence=0.002,
        reason="tiny but approved",
    )

    review = controller.review(signal, cash_balance=55000, latest_price=1000)

    assert review["target_notional"] == 5000
    assert review["size_scale"] == 5.0


def test_broker_rejects_buy_when_symbol_exposure_limit_is_reached():
    broker = PaperBroker(
        starting_cash=10000,
        trading_fee_pct=0.0,
        slippage_pct=0.0,
        min_order_notional=1,
        max_symbol_exposure_pct=10,
    )

    first = broker.submit(
        {
            "strategy_name": "trend_following",
            "symbol": "BTC/KRW",
            "action": "buy",
            "confidence": 1.0,
            "size_scale": 5.0,
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
            "size_scale": 6.0,
            "reason": "buy-more",
        },
        execution_price=100,
    )

    assert first["status"] == "recorded"
    assert second["status"] == "rejected"
    assert second["reason"] == "max_symbol_exposure_reached"
