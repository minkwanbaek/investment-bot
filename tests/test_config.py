from investment_bot.core.settings import get_settings
from investment_bot.services.container import get_paper_broker, get_risk_controller
from investment_bot.strategies.registry import list_enabled_strategies


def setup_function():
    get_settings.cache_clear()
    get_paper_broker.cache_clear()
    get_risk_controller.cache_clear()
    # Set environment to override config for tests
    import os
    os.environ.pop("INVESTMENT_BOT_TRADING_MODE", None)
    os.environ.pop("INVESTMENT_BOT_RISK_CONTROL_RISK_PER_TRADE_PCT", None)


def test_file_config_is_loaded():
    settings = get_settings()
    assert settings.app_name == "investment-bot"
    assert settings.trading_mode == "live"  # config/app.yml sets live mode
    assert settings.symbols == ["BTC/KRW", "ETH/KRW", "SOL/KRW", "XRP/KRW", "ADA/KRW", "DOGE/KRW", "XLM/KRW", "TRX/KRW", "HBAR/KRW", "LINK/KRW", "APT/KRW", "SUI/KRW", "AVAX/KRW", "DOT/KRW", "SEI/KRW", "ONDO/KRW", "ENA/KRW", "WLD/KRW", "ARB/KRW", "OP/KRW"]
    assert settings.starting_cash == 10_000_000
    assert settings.max_risk_per_trade_pct == 20.0  # config sets 20.0


def test_enabled_strategies_follow_config():
    assert list_enabled_strategies() == ["dca", "mean_reversion", "trend_following"]


def test_services_reflect_config_values():
    broker = get_paper_broker()
    risk_controller = get_risk_controller()
    assert broker.starting_cash == 10_000_000
    assert broker.trading_fee_pct == 0.05
    assert broker.slippage_pct == 0.05
    # Risk controller max_confidence_position_scale is set from settings.auto_trade_target_allocation_pct / 100
    # config/app.yml sets target_allocation_pct=20.0, so scale=0.2
    assert risk_controller.max_confidence_position_scale == 0.2
