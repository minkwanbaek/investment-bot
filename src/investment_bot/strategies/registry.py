from investment_bot.core.settings import get_settings
from investment_bot.strategies.dca import DCAStrategy
from investment_bot.strategies.mean_reversion import MeanReversionStrategy
from investment_bot.strategies.trend_following import TrendFollowingStrategy

REGISTERED_STRATEGIES = {
    "trend_following": TrendFollowingStrategy,
    "mean_reversion": MeanReversionStrategy,
    "dca": DCAStrategy,
}


def list_registered_strategies() -> list[str]:
    return sorted(REGISTERED_STRATEGIES.keys())


def list_enabled_strategies() -> list[str]:
    settings = get_settings()
    return [name for name in settings.enabled_strategies if name in REGISTERED_STRATEGIES]
