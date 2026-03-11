from investment_bot.core.settings import get_settings
from investment_bot.services.container import get_paper_broker, get_risk_controller
from investment_bot.strategies.registry import list_enabled_strategies


def setup_function():
    get_settings.cache_clear()
    get_paper_broker.cache_clear()
    get_risk_controller.cache_clear()


def test_file_config_is_loaded():
    settings = get_settings()
    assert settings.app_name == "investment-bot"
    assert settings.trading_mode == "paper"
    assert settings.symbols == ["BTC/KRW"]
    assert settings.starting_cash == 10_000_000
    assert settings.max_risk_per_trade_pct == 1.0


def test_enabled_strategies_follow_config():
    assert list_enabled_strategies() == ["dca", "mean_reversion", "trend_following"]


def test_services_reflect_config_values():
    broker = get_paper_broker()
    risk_controller = get_risk_controller()
    assert broker.starting_cash == 10_000_000
    assert risk_controller.max_confidence_position_scale == 0.01
