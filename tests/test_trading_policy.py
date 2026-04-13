from investment_bot.core.settings import Settings
from investment_bot.core.trading_policy import build_trading_policy


def test_trading_policy_normalizes_legacy_regime_aliases():
    policy = build_trading_policy(Settings())

    assert policy.normalize_regime("uptrend") == "trend_up"
    assert policy.normalize_regime("downtrend") == "trend_down"
    assert policy.normalize_regime("ranging") == "sideways"
    assert policy.normalize_regime("mixed") == "uncertain"
    assert policy.normalize_regime("unknown") == "uncertain"


def test_trading_policy_snapshot_collects_core_axes():
    settings = Settings(
        max_consecutive_buys=5,
        max_symbol_exposure_pct=25.0,
        auto_trade_meaningful_order_notional=8000.0,
        auto_trade_min_managed_position_notional=1500.0,
        auto_trade_max_total_exposure_pct=80.0,
        auto_trade_target_allocation_pct=20.0,
        trend_strategy_allowed_regimes=["uptrend", "downtrend"],
        range_strategy_allowed_regimes=["ranging"],
    )
    snapshot = build_trading_policy(settings).snapshot

    assert snapshot.max_consecutive_buys == 5
    assert snapshot.max_symbol_exposure_pct == 25.0
    assert snapshot.meaningful_order_notional == 8000.0
    assert snapshot.min_managed_position_notional == 1500.0
    assert snapshot.max_total_exposure_pct == 80.0
    assert snapshot.target_allocation_pct == 20.0
    assert snapshot.trend_strategy_allowed_regimes == ("trend_up", "trend_down")
    assert snapshot.range_strategy_allowed_regimes == ("sideways",)
