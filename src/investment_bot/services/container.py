from functools import lru_cache

from investment_bot.core.settings import get_settings
from investment_bot.risk.controller import RiskController
from investment_bot.services.paper_broker import PaperBroker
from investment_bot.services.trading_cycle import TradingCycleService


@lru_cache
def get_paper_broker() -> PaperBroker:
    settings = get_settings()
    return PaperBroker(starting_cash=settings.starting_cash)


@lru_cache
def get_risk_controller() -> RiskController:
    settings = get_settings()
    return RiskController(max_confidence_position_scale=settings.max_risk_per_trade_pct / 100)


@lru_cache
def get_trading_cycle_service() -> TradingCycleService:
    return TradingCycleService(
        risk_controller=get_risk_controller(),
        paper_broker=get_paper_broker(),
    )
