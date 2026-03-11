from investment_bot.core.settings import Settings
from investment_bot.services.config_service import ConfigService


def test_config_service_exposes_live_mode_controls():
    result = ConfigService(
        settings=Settings(
            starting_cash=1000,
            max_risk_per_trade_pct=1.0,
            max_daily_loss_pct=3.0,
            max_drawdown_pct=10.0,
            symbols=["BTC/KRW"],
            enabled_strategies=["trend_following"],
            live_mode="shadow",
            confirm_live_trading=False,
        )
    ).validate()
    assert result["resolved"]["live_mode"] == "shadow"
    assert result["resolved"]["confirm_live_trading"] is False
