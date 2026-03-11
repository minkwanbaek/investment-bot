from functools import lru_cache

from investment_bot.core.settings import get_settings
from investment_bot.market_data.registry import build_default_market_data_registry
from investment_bot.risk.controller import RiskController
from investment_bot.services.alert_service import AlertService
from investment_bot.services.backtest_service import BacktestService
from investment_bot.services.candle_store import CandleStore
from investment_bot.services.config_service import ConfigService
from investment_bot.services.ledger_store import LedgerStore
from investment_bot.services.market_data_service import MarketDataService
from investment_bot.services.metrics_service import MetricsService
from investment_bot.services.paper_broker import PaperBroker
from investment_bot.services.run_history_service import RunHistoryService
from investment_bot.services.run_history_store import RunHistoryStore
from investment_bot.services.trading_cycle import TradingCycleService


@lru_cache
def get_market_data_service() -> MarketDataService:
    settings = get_settings()
    return MarketDataService(
        registry=build_default_market_data_registry(),
        candle_store=CandleStore(settings.candle_store_path),
    )


@lru_cache
def get_paper_broker() -> PaperBroker:
    settings = get_settings()
    return PaperBroker(
        starting_cash=settings.starting_cash,
        ledger_store=LedgerStore(settings.ledger_path),
        trading_fee_pct=settings.trading_fee_pct,
        slippage_pct=settings.slippage_pct,
    )


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


@lru_cache
def get_metrics_service() -> MetricsService:
    return MetricsService()


@lru_cache
def get_alert_service() -> AlertService:
    settings = get_settings()
    return AlertService(
        unrealized_pnl_threshold=-(settings.starting_cash * (settings.max_daily_loss_pct / 100)),
        drawdown_pct_threshold=settings.max_drawdown_pct,
    )


@lru_cache
def get_config_service() -> ConfigService:
    return ConfigService(settings=get_settings())


@lru_cache
def get_run_history_service() -> RunHistoryService:
    settings = get_settings()
    return RunHistoryService(store=RunHistoryStore(settings.run_history_path))


@lru_cache
def get_backtest_service() -> BacktestService:
    return BacktestService(
        market_data_service=get_market_data_service(),
        paper_broker=get_paper_broker(),
        trading_cycle_service=get_trading_cycle_service(),
        metrics_service=get_metrics_service(),
    )
