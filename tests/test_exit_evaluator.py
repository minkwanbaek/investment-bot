from datetime import datetime, timedelta, timezone

from investment_bot.core.settings import Settings
from investment_bot.features.exit.application.evaluator import ExitEvaluator
from investment_bot.features.exit.domain.models import MarketSnapshot, PositionSnapshot


def test_exit_evaluator_triggers_partial_take_profit_and_updates_trailing_state(monkeypatch):
    settings = Settings(
        partial_take_profit_enabled=True,
        trailing_stop_enabled=True,
        tp1_size_pct=0.5,
        trailing_distance_ratio=0.01,
    )
    evaluator = ExitEvaluator(settings=settings, min_order_notional=5000.0, slippage_pct=0.05)

    decision = evaluator.evaluate_position_exit(
        PositionSnapshot(
            symbol="BTC/KRW",
            quantity=1.0,
            average_price=10000.0,
            tp1_done=False,
            tp1_price=10300.0,
        ),
        MarketSnapshot(latest_price=10350.0, now=datetime.now(timezone.utc)),
    )

    assert decision.triggered is True
    assert decision.exit_reason == "partial_take_profit"
    assert decision.priority == "profit_take"
    assert decision.quantity == 0.5
    assert decision.metadata["position_updates"]["trailing_active"] is True
    assert decision.metadata["position_updates"]["trailing_stop_price"] == 10246.5


def test_exit_evaluator_triggers_timeout_exit():
    settings = Settings(timeout_exit_enabled=True, max_holding_minutes=60, min_progress_pct=0.003)
    evaluator = ExitEvaluator(settings=settings, min_order_notional=5000.0, slippage_pct=0.05)

    decision = evaluator.evaluate_position_exit(
        PositionSnapshot(
            symbol="BTC/KRW",
            quantity=1.0,
            average_price=10000.0,
            opened_at=datetime.now(timezone.utc) - timedelta(minutes=120),
        ),
        MarketSnapshot(latest_price=10020.0, now=datetime.now(timezone.utc)),
    )

    assert decision.triggered is True
    assert decision.exit_reason == "timeout"
    assert decision.priority == "protective"


def test_exit_evaluator_triggers_strategy_trend_reversal_exit():
    settings = Settings()
    evaluator = ExitEvaluator(settings=settings, min_order_notional=5000.0, slippage_pct=0.05)

    decision = evaluator.evaluate_strategy_exit(
        position=PositionSnapshot(
            symbol="BTC/KRW",
            quantity=1.0,
            average_price=10000.0,
        ),
        market=MarketSnapshot(latest_price=10050.0, trend_reversal=True),
        stop_loss_pct=-0.015,
        take_profit_pct=0.05,
    )

    assert decision.triggered is True
    assert decision.exit_reason == "trend_reversal"
    assert decision.priority == "soft_exit"


def test_exit_evaluator_triggers_managed_rebound_exit():
    settings = Settings()
    evaluator = ExitEvaluator(settings=settings, min_order_notional=5000.0, slippage_pct=0.05)

    decision = evaluator.evaluate_strategy_exit(
        position=PositionSnapshot(
            symbol="ETH/KRW",
            quantity=2.0,
            average_price=100.0,
        ),
        market=MarketSnapshot(latest_price=101.3),
        managed_rebound_exit_threshold=0.008,
        managed_rebound_exit_reason="mean_reversion_managed_rebound_exit",
    )

    assert decision.triggered is True
    assert decision.exit_reason == "mean_reversion_managed_rebound_exit"
    assert decision.priority == "soft_exit"
    assert decision.confidence == 0.6


def test_exit_evaluator_live_override_triggers_take_profit_trailing_stop():
    settings = Settings(
        auto_trade_stop_loss_pct=1.5,
        auto_trade_partial_take_profit_pct=2.0,
        auto_trade_trailing_stop_pct=1.0,
        auto_trade_partial_sell_ratio=0.5,
    )
    evaluator = ExitEvaluator(settings=settings, min_order_notional=5000.0, slippage_pct=0.05)

    decision = evaluator.evaluate_live_exit_override(
        balance=1.0,
        avg_buy_price=100.0,
        latest_price=101.0,
        peak_price=104.0,
    )

    assert decision.triggered is True
    assert decision.reason == "take_profit_trailing_stop"
    assert decision.sell_ratio == 0.5
    assert decision.next_peak_price == 104.0
