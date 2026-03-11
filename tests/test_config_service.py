from investment_bot.core.settings import Settings
from investment_bot.services.config_service import ConfigService


def test_config_service_validates_good_settings():
    result = ConfigService(
        settings=Settings(
            starting_cash=1000,
            max_risk_per_trade_pct=1.0,
            max_daily_loss_pct=3.0,
            max_drawdown_pct=10.0,
            symbols=["BTC/KRW"],
            enabled_strategies=["trend_following"],
        )
    ).validate()
    assert result["valid"] is True
    assert result["issues"] == []


def test_config_service_detects_invalid_settings():
    result = ConfigService(
        settings=Settings(
            starting_cash=0,
            max_risk_per_trade_pct=0,
            max_daily_loss_pct=0,
            max_drawdown_pct=0,
            symbols=[],
            enabled_strategies=["unknown_strategy"],
        )
    ).validate()
    assert result["valid"] is False
    assert len(result["issues"]) >= 5
