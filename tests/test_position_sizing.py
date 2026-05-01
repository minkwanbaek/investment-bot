from investment_bot.models.signal import TradeSignal
from investment_bot.risk.controller import RiskController
from investment_bot.services.paper_broker import PaperBroker


def test_risk_controller_sizes_from_cash_balance_and_price(monkeypatch):
    from investment_bot.core.settings import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    monkeypatch.setattr(settings, "risk_control_risk_per_trade_pct", 0.005)

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


def test_risk_controller_does_not_base_floor_weak_confidence_buy():
    controller = RiskController(max_confidence_position_scale=0.075, min_order_notional=5000, base_entry_notional=10000)
    signal = TradeSignal(
        strategy_name="trend_following",
        symbol="BTC/KRW",
        action="buy",
        confidence=0.2,
        reason="weak buy",
    )

    review = controller.review(signal, cash_balance=100000, latest_price=1000)

    assert review["target_notional"] == 5000
    assert review["size_scale"] == 5.0


def test_risk_controller_preserves_executable_min_order_after_high_volatility_haircut(monkeypatch):
    from investment_bot.core.settings import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    monkeypatch.setattr(settings, "blocked_hours", [])
    monkeypatch.setattr(settings, "high_volatility_defense_enabled", True)
    monkeypatch.setattr(settings, "volatility_size_multipliers", {"low": 1.0, "normal": 1.0, "high": 0.5})
    monkeypatch.setattr(settings, "risk_control_risk_per_trade_pct", 0.01)

    controller = RiskController(max_confidence_position_scale=0.075, min_order_notional=5000, base_entry_notional=10000)
    signal = TradeSignal(
        strategy_name="trend_following",
        symbol="BTC/KRW",
        action="buy",
        confidence=0.49,
        reason="high-vol continuation",
    )
    signal.meta = {"volatility_state": "high", "losing_streak": 0}

    review = controller.review(signal, cash_balance=100000, latest_price=1000)

    assert review["target_notional"] == 5000
    assert review["size_scale"] == 5.0


def test_high_volatility_size_uses_configured_multiplier_once(monkeypatch):
    from investment_bot.core.settings import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    monkeypatch.setattr(settings, "blocked_hours", [])
    monkeypatch.setattr(settings, "high_volatility_defense_enabled", True)
    monkeypatch.setattr(settings, "volatility_size_multipliers", {"low": 1.0, "normal": 1.0, "high": 0.5})
    monkeypatch.setattr(settings, "risk_control_risk_per_trade_pct", 0.01)

    controller = RiskController(max_confidence_position_scale=0.1, min_order_notional=5000, base_entry_notional=10000)
    signal = TradeSignal(
        strategy_name="trend_following",
        symbol="BTC/KRW",
        action="buy",
        confidence=1.0,
        reason="high-vol breakout",
    )
    signal.meta = {"volatility_state": "high", "losing_streak": 0}

    review = controller.review(signal, cash_balance=10_000_000, latest_price=1000)

    assert review["target_notional"] == 500000
    assert review["size_scale"] == 500.0


def test_losing_streak_risk_mode_can_reduce_below_min_order(monkeypatch):
    from investment_bot.core.settings import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    monkeypatch.setattr(settings, "blocked_hours", [])
    monkeypatch.setattr(settings, "risk_control_risk_per_trade_pct", 0.01)
    monkeypatch.setattr(settings, "losing_streak_threshold_reduced", 2)
    monkeypatch.setattr(settings, "risk_mode_multipliers", {"normal": 1.0, "reduced": 0.5, "minimal": 0.25})

    controller = RiskController(max_confidence_position_scale=0.075, min_order_notional=5000, base_entry_notional=10000)
    signal = TradeSignal(
        strategy_name="trend_following",
        symbol="BTC/KRW",
        action="buy",
        confidence=0.49,
        reason="post-loss continuation",
    )
    signal.meta = {"volatility_state": "normal", "losing_streak": 2}

    review = controller.review(signal, cash_balance=100000, latest_price=1000)

    assert review["risk_mode"] == "reduced"
    assert review["target_notional"] == 2500
    assert review["size_scale"] == 2.5


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
