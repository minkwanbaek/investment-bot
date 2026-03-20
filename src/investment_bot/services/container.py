from functools import lru_cache

from investment_bot.core.settings import get_settings
from investment_bot.market_data.registry import build_default_market_data_registry
from investment_bot.risk.controller import RiskController
from investment_bot.services.account_service import AccountService
from investment_bot.services.alert_service import AlertService
from investment_bot.services.auto_trade_service import AutoTradeService
from investment_bot.services.backtest_service import BacktestService
from investment_bot.services.candle_store import CandleStore
from investment_bot.services.config_service import ConfigService
from investment_bot.services.drift_report_service import DriftReportService
from investment_bot.services.exchange_rules_service import ExchangeRulesService
from investment_bot.services.fail_safe_service import FailSafeService
from investment_bot.services.ledger_store import LedgerStore
from investment_bot.services.live_execution_service import LiveExecutionService
from investment_bot.services.market_data_service import MarketDataService
from investment_bot.services.metrics_service import MetricsService
from investment_bot.services.paper_broker import PaperBroker
from investment_bot.services.run_history_service import RunHistoryService
from investment_bot.services.run_history_store import RunHistoryStore
from investment_bot.services.scheduler_service import SchedulerService
from investment_bot.services.semi_live_service import SemiLiveService
from investment_bot.services.shadow_service import ShadowService
from investment_bot.services.trading_cycle import TradingCycleService
from investment_bot.services.upbit_client import UpbitClient
from investment_bot.services.visualization_service import VisualizationService


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
        min_order_notional=settings.min_order_notional,
        max_consecutive_buys=settings.max_consecutive_buys,
        max_symbol_exposure_pct=settings.max_symbol_exposure_pct,
    )


@lru_cache
def get_risk_controller() -> RiskController:
    settings = get_settings()
    return RiskController(
        max_confidence_position_scale=settings.max_risk_per_trade_pct / 100,
        min_order_notional=max(settings.min_order_notional, 5000.0 if settings.base_currency == "KRW" else 0.0),
    )


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
def get_visualization_service() -> VisualizationService:
    return VisualizationService(run_history_service=get_run_history_service())


@lru_cache
def get_upbit_client() -> UpbitClient:
    settings = get_settings()
    return UpbitClient(access_key=settings.upbit_access_key, secret_key=settings.upbit_secret_key)


@lru_cache
def get_account_service() -> AccountService:
    return AccountService(upbit_client=get_upbit_client())


@lru_cache
def get_exchange_rules_service() -> ExchangeRulesService:
    return ExchangeRulesService(upbit_client=get_upbit_client())


@lru_cache
def get_drift_report_service() -> DriftReportService:
    return DriftReportService(
        run_history_service=get_run_history_service(),
        paper_broker=get_paper_broker(),
    )


@lru_cache
def get_live_execution_service() -> LiveExecutionService:
    settings = get_settings()
    return LiveExecutionService(
        upbit_client=get_upbit_client(),
        exchange_rules_service=get_exchange_rules_service(),
        run_history_service=get_run_history_service(),
        account_service=get_account_service(),
        live_mode=settings.live_mode,
        confirm_live_trading=settings.confirm_live_trading,
    )


@lru_cache
def get_backtest_service() -> BacktestService:
    return BacktestService(
        market_data_service=get_market_data_service(),
        paper_broker=get_paper_broker(),
        trading_cycle_service=get_trading_cycle_service(),
        metrics_service=get_metrics_service(),
    )


@lru_cache
def get_semi_live_service() -> SemiLiveService:
    return SemiLiveService(
        market_data_service=get_market_data_service(),
        trading_cycle_service=get_trading_cycle_service(),
        run_history_service=get_run_history_service(),
    )


@lru_cache
def get_fail_safe_service() -> FailSafeService:
    return FailSafeService(
        alert_service=get_alert_service(),
        max_alerts_per_batch=1,
        max_loss_steps=2,
    )


@lru_cache
def get_shadow_service() -> ShadowService:
    return ShadowService(
        semi_live_service=get_semi_live_service(),
        run_history_service=get_run_history_service(),
        upbit_client=get_upbit_client(),
        account_service=get_account_service(),
    )


@lru_cache
def get_scheduler_service() -> SchedulerService:
    return SchedulerService(
        semi_live_service=get_semi_live_service(),
        run_history_service=get_run_history_service(),
        fail_safe_service=get_fail_safe_service(),
    )


@lru_cache
def get_auto_trade_service() -> AutoTradeService:
    return AutoTradeService(
        settings=get_settings(),
        shadow_service=get_shadow_service(),
        live_execution_service=get_live_execution_service(),
        account_service=get_account_service(),
        run_history_service=get_run_history_service(),
        strategy_selection_service=StrategySelectionService(),
    )
history_service(),
    )
