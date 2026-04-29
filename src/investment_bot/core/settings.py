from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import AliasChoices, BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseModel):
    name: str = "investment-bot"
    environment: str = "local"


class TradingConfig(BaseModel):
    mode: str = "paper"
    base_currency: str = "KRW"
    symbols: list[str] = Field(default_factory=lambda: ["BTC/KRW"])
    dynamic_symbol_selection: bool = False
    dynamic_symbol_top_n: int = 10
    starting_cash: float = 10_000_000
    min_order_notional: float = 0.0
    max_consecutive_buys: int = 3
    max_symbol_exposure_pct: float = 25.0


class RiskConfig(BaseModel):
    max_risk_per_trade_pct: float = 1.0
    max_daily_loss_pct: float = 3.0
    max_drawdown_pct: float = 10.0


class StrategyToggleConfig(BaseModel):
    enabled: bool = True


class AutoTradeConfig(BaseModel):
    enabled: bool = False
    strategy_version: str = "v1.0-base"
    symbol: str = "BTC/KRW"
    strategy_name: str = "trend_following"
    timeframe: str = "1h"
    limit: int = 5
    interval_seconds: int = 300
    min_krw_balance: float = 15000.0
    base_entry_notional: float = 10000.0
    target_allocation_pct: float = 20.0
    meaningful_order_notional: float = 10000.0
    max_pending_seconds: int = 600
    cooldown_cycles: int = 1
    stop_loss_pct: float = 1.5
    partial_take_profit_pct: float = 2.0
    trailing_stop_pct: float = 1.0
    partial_sell_ratio: float = 0.5
    max_total_exposure_pct: float = 60.0
    min_managed_position_notional: float = 10000.0


class LiveConfig(BaseModel):
    confirm_live_trading: bool = False


class SidewayFilterConfig(BaseModel):
    enabled: bool = True
    trend_gap_threshold: float = 0.0015
    range_threshold: float = 0.01
    volatility_block_on_low: bool = True
    breakout_exception_enabled: bool = False
    breakout_exception_momentum_min: float = 0.0
    breakout_exception_trend_gap_ratio: float = 0.7
    breakout_exception_allow_bearish_higher_tf: bool = False
    breakout_exception_allow_low_volatility: bool = False


class StrategyRouteConfig(BaseModel):
    trend_strategy_allowed_regimes: list[str] = Field(default_factory=lambda: ["uptrend", "downtrend"])
    range_strategy_allowed_regimes: list[str] = Field(default_factory=lambda: ["sideways"])
    uncertain_block_enabled: bool = True


class RiskControlConfig(BaseModel):
    higher_tf_bias_filter_enabled: bool = True
    high_volatility_defense_enabled: bool = True
    time_blacklist_filter_enabled: bool = True
    blocked_hours: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])
    risk_per_trade_pct: float = 0.005
    volatility_size_multipliers: dict[str, float] = Field(default_factory=lambda: {"low": 1.0, "normal": 1.0, "high": 0.5})
    losing_streak_threshold_reduced: int = 2
    losing_streak_threshold_minimal: int = 4
    risk_mode_multipliers: dict[str, float] = Field(default_factory=lambda: {"normal": 1.0, "reduced": 0.5, "minimal": 0.25})


class BrokerExitConfig(BaseModel):
    atr_stop_enabled: bool = True
    stop_atr_multiplier: float = 2.0
    partial_take_profit_enabled: bool = True
    tp1_ratio: float = 0.03
    tp1_size_pct: float = 0.5
    trailing_stop_enabled: bool = True
    trailing_activation_ratio: float = 0.02
    trailing_distance_ratio: float = 0.01
    timeout_exit_enabled: bool = True
    max_holding_minutes: int = 60
    min_progress_pct: float = 0.005


class StandardBacktestConfig(BaseModel):
    fee_model: str = "paper_broker_fee_pct"
    slippage_model: str = "paper_broker_slippage_pct"


class FileConfig(BaseModel):
    app: AppConfig = Field(default_factory=AppConfig)
    trading: TradingConfig = Field(default_factory=TradingConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    auto_trade: AutoTradeConfig = Field(default_factory=AutoTradeConfig)
    live: LiveConfig = Field(default_factory=LiveConfig)
    sideway_filter: SidewayFilterConfig = Field(default_factory=SidewayFilterConfig)
    strategy_route: StrategyRouteConfig = Field(default_factory=StrategyRouteConfig)
    risk_control: RiskControlConfig = Field(default_factory=RiskControlConfig)
    broker_exit: BrokerExitConfig = Field(default_factory=BrokerExitConfig)
    standard_backtest: StandardBacktestConfig = Field(default_factory=StandardBacktestConfig)
    strategies: dict[str, StrategyToggleConfig] = Field(default_factory=dict)


class Settings(BaseSettings):
    config_path: str = "config/app.yml"
    app_name: str = "investment-bot"
    environment: str = "local"
    trading_mode: str = "paper"
    base_currency: str = "KRW"
    symbols: list[str] = Field(default_factory=lambda: ["BTC/KRW"])
    dynamic_symbol_selection: bool = False
    dynamic_symbol_top_n: int = 10
    starting_cash: float = 10_000_000
    min_order_notional: float = 0.0
    max_consecutive_buys: int = 3
    max_symbol_exposure_pct: float = 25.0
    ledger_path: str = "data/paper_ledger.json"
    candle_store_path: str = "data/candles.json"
    run_history_path: str = "data/run_history.json"
    upbit_access_key: str = Field(default="", validation_alias=AliasChoices("UPBIT_ACCESS_KEY", "UPBIT_ACCESS_API_KEY"))
    upbit_secret_key: str = Field(default="", validation_alias=AliasChoices("UPBIT_SECRET_KEY", "UPBIT_SECRET_API_KEY"))
    live_mode: str = Field(default="shadow", validation_alias="INVESTMENT_BOT_LIVE_MODE")
    confirm_live_trading: bool = False
    trading_fee_pct: float = 0.05
    slippage_pct: float = 0.05
    max_risk_per_trade_pct: float = 1.0
    max_daily_loss_pct: float = 3.0
    max_drawdown_pct: float = 10.0
    auto_trade_enabled: bool = False
    auto_trade_strategy_version: str = "v1.0-base"
    auto_trade_symbol: str = "BTC/KRW"
    auto_trade_strategy_name: str = "trend_following"
    auto_trade_timeframe: str = "1h"
    auto_trade_limit: int = 5
    auto_trade_interval_seconds: int = 300
    auto_trade_min_krw_balance: float = 15000.0
    auto_trade_base_entry_notional: float = 10000.0
    auto_trade_target_allocation_pct: float = 20.0
    auto_trade_meaningful_order_notional: float = 10000.0
    auto_trade_max_pending_seconds: int = 600
    auto_trade_cooldown_cycles: int = 1
    auto_trade_stop_loss_pct: float = 1.5
    auto_trade_partial_take_profit_pct: float = 2.0
    auto_trade_trailing_stop_pct: float = 1.0
    auto_trade_partial_sell_ratio: float = 0.5
    auto_trade_max_total_exposure_pct: float = 60.0
    auto_trade_min_managed_position_notional: float = 10000.0
    enabled_strategies: list[str] = Field(default_factory=lambda: ["trend_following", "mean_reversion", "dca"])
    sideway_filter_enabled: bool = True
    sideway_filter_trend_gap_threshold: float = 0.0015
    sideway_filter_range_threshold: float = 0.01
    sideway_filter_volatility_block_on_low: bool = True
    sideway_filter_breakout_exception_enabled: bool = False
    sideway_filter_breakout_exception_momentum_min: float = 0.0
    sideway_filter_breakout_exception_trend_gap_ratio: float = 0.7
    sideway_filter_breakout_exception_allow_bearish_higher_tf: bool = False
    sideway_filter_breakout_exception_allow_low_volatility: bool = False
    trend_strategy_allowed_regimes: list[str] = Field(default_factory=lambda: ["uptrend", "downtrend"])
    range_strategy_allowed_regimes: list[str] = Field(default_factory=lambda: ["sideways"])
    uncertain_block_enabled: bool = True
    higher_tf_bias_filter_enabled: bool = True
    high_volatility_defense_enabled: bool = True
    time_blacklist_filter_enabled: bool = True
    blocked_hours: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])
    risk_control_risk_per_trade_pct: float = 0.005
    volatility_size_multipliers: dict[str, float] = Field(default_factory=lambda: {"low": 1.0, "normal": 1.0, "high": 0.5})
    losing_streak_threshold_reduced: int = 2
    losing_streak_threshold_minimal: int = 4
    risk_mode_multipliers: dict[str, float] = Field(default_factory=lambda: {"normal": 1.0, "reduced": 0.5, "minimal": 0.25})
    atr_stop_enabled: bool = True
    stop_atr_multiplier: float = 2.0
    partial_take_profit_enabled: bool = True
    tp1_ratio: float = 0.03
    tp1_size_pct: float = 0.5
    trailing_stop_enabled: bool = True
    trailing_activation_ratio: float = 0.02
    trailing_distance_ratio: float = 0.01
    timeout_exit_enabled: bool = True
    max_holding_minutes: int = 60
    min_progress_pct: float = 0.005
    standard_backtest_fee_model: str = "paper_broker_fee_pct"
    standard_backtest_slippage_model: str = "paper_broker_slippage_pct"

    model_config = SettingsConfigDict(
        env_prefix="INVESTMENT_BOT_",
        env_file=".env",
        extra="ignore",
        populate_by_name=True,
    )


@lru_cache
def get_settings() -> Settings:
    raw_settings = Settings()
    config_file = Path(raw_settings.config_path)

    if not config_file.is_absolute():
        config_file = Path.cwd() / config_file

    if not config_file.exists():
        return raw_settings

    with config_file.open("r", encoding="utf-8") as handle:
        loaded: dict[str, Any] = yaml.safe_load(handle) or {}

    file_config = FileConfig.model_validate(loaded)
    enabled_strategies = sorted(
        name for name, config in file_config.strategies.items() if config.enabled
    ) or raw_settings.enabled_strategies

    return Settings(
        config_path=raw_settings.config_path,
        app_name=file_config.app.name,
        environment=file_config.app.environment,
        trading_mode=file_config.trading.mode,
        base_currency=file_config.trading.base_currency,
        symbols=file_config.trading.symbols,
        dynamic_symbol_selection=file_config.trading.dynamic_symbol_selection,
        dynamic_symbol_top_n=file_config.trading.dynamic_symbol_top_n,
        starting_cash=file_config.trading.starting_cash,
        min_order_notional=file_config.trading.min_order_notional,
        max_consecutive_buys=file_config.trading.max_consecutive_buys,
        max_symbol_exposure_pct=file_config.trading.max_symbol_exposure_pct,
        ledger_path=raw_settings.ledger_path,
        candle_store_path=raw_settings.candle_store_path,
        run_history_path=raw_settings.run_history_path,
        upbit_access_key=raw_settings.upbit_access_key,
        upbit_secret_key=raw_settings.upbit_secret_key,
        live_mode=file_config.trading.mode,
        confirm_live_trading=file_config.live.confirm_live_trading,
        trading_fee_pct=raw_settings.trading_fee_pct,
        slippage_pct=raw_settings.slippage_pct,
        max_risk_per_trade_pct=file_config.risk.max_risk_per_trade_pct,
        max_daily_loss_pct=file_config.risk.max_daily_loss_pct,
        max_drawdown_pct=file_config.risk.max_drawdown_pct,
        auto_trade_enabled=file_config.auto_trade.enabled,
        auto_trade_strategy_version=file_config.auto_trade.strategy_version,
        auto_trade_symbol=file_config.auto_trade.symbol,
        auto_trade_strategy_name=file_config.auto_trade.strategy_name,
        auto_trade_timeframe=file_config.auto_trade.timeframe,
        auto_trade_limit=file_config.auto_trade.limit,
        auto_trade_interval_seconds=file_config.auto_trade.interval_seconds,
        auto_trade_min_krw_balance=file_config.auto_trade.min_krw_balance,
        auto_trade_base_entry_notional=file_config.auto_trade.base_entry_notional,
        auto_trade_target_allocation_pct=file_config.auto_trade.target_allocation_pct,
        auto_trade_meaningful_order_notional=file_config.auto_trade.meaningful_order_notional,
        auto_trade_max_pending_seconds=file_config.auto_trade.max_pending_seconds,
        auto_trade_cooldown_cycles=file_config.auto_trade.cooldown_cycles,
        auto_trade_stop_loss_pct=file_config.auto_trade.stop_loss_pct,
        auto_trade_partial_take_profit_pct=file_config.auto_trade.partial_take_profit_pct,
        auto_trade_trailing_stop_pct=file_config.auto_trade.trailing_stop_pct,
        auto_trade_partial_sell_ratio=file_config.auto_trade.partial_sell_ratio,
        auto_trade_max_total_exposure_pct=file_config.auto_trade.max_total_exposure_pct,
        auto_trade_min_managed_position_notional=file_config.auto_trade.min_managed_position_notional,
        enabled_strategies=enabled_strategies,
        sideway_filter_enabled=file_config.sideway_filter.enabled,
        sideway_filter_trend_gap_threshold=file_config.sideway_filter.trend_gap_threshold,
        sideway_filter_range_threshold=file_config.sideway_filter.range_threshold,
        sideway_filter_volatility_block_on_low=file_config.sideway_filter.volatility_block_on_low,
        sideway_filter_breakout_exception_enabled=file_config.sideway_filter.breakout_exception_enabled,
        sideway_filter_breakout_exception_momentum_min=file_config.sideway_filter.breakout_exception_momentum_min,
        sideway_filter_breakout_exception_trend_gap_ratio=file_config.sideway_filter.breakout_exception_trend_gap_ratio,
        sideway_filter_breakout_exception_allow_bearish_higher_tf=file_config.sideway_filter.breakout_exception_allow_bearish_higher_tf,
        sideway_filter_breakout_exception_allow_low_volatility=file_config.sideway_filter.breakout_exception_allow_low_volatility,
        trend_strategy_allowed_regimes=file_config.strategy_route.trend_strategy_allowed_regimes,
        range_strategy_allowed_regimes=file_config.strategy_route.range_strategy_allowed_regimes,
        uncertain_block_enabled=file_config.strategy_route.uncertain_block_enabled,
        higher_tf_bias_filter_enabled=file_config.risk_control.higher_tf_bias_filter_enabled,
        high_volatility_defense_enabled=file_config.risk_control.high_volatility_defense_enabled,
        time_blacklist_filter_enabled=file_config.risk_control.time_blacklist_filter_enabled,
        blocked_hours=file_config.risk_control.blocked_hours,
        risk_control_risk_per_trade_pct=file_config.risk_control.risk_per_trade_pct,
        volatility_size_multipliers=file_config.risk_control.volatility_size_multipliers,
        losing_streak_threshold_reduced=file_config.risk_control.losing_streak_threshold_reduced,
        losing_streak_threshold_minimal=file_config.risk_control.losing_streak_threshold_minimal,
        risk_mode_multipliers=file_config.risk_control.risk_mode_multipliers,
        atr_stop_enabled=file_config.broker_exit.atr_stop_enabled,
        stop_atr_multiplier=file_config.broker_exit.stop_atr_multiplier,
        partial_take_profit_enabled=file_config.broker_exit.partial_take_profit_enabled,
        tp1_ratio=file_config.broker_exit.tp1_ratio,
        tp1_size_pct=file_config.broker_exit.tp1_size_pct,
        trailing_stop_enabled=file_config.broker_exit.trailing_stop_enabled,
        trailing_activation_ratio=file_config.broker_exit.trailing_activation_ratio,
        trailing_distance_ratio=file_config.broker_exit.trailing_distance_ratio,
        timeout_exit_enabled=file_config.broker_exit.timeout_exit_enabled,
        max_holding_minutes=file_config.broker_exit.max_holding_minutes,
        min_progress_pct=file_config.broker_exit.min_progress_pct,
        standard_backtest_fee_model=file_config.standard_backtest.fee_model,
        standard_backtest_slippage_model=file_config.standard_backtest.slippage_model,
    )
