from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseModel):
    name: str = "investment-bot"
    environment: str = "local"


class TradingConfig(BaseModel):
    mode: str = "paper"
    base_currency: str = "KRW"
    symbols: list[str] = Field(default_factory=lambda: ["BTC/KRW"])
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
    symbol: str = "BTC/KRW"
    strategy_name: str = "trend_following"
    timeframe: str = "1h"
    limit: int = 5
    interval_seconds: int = 300
    min_krw_balance: float = 15000.0
    target_allocation_pct: float = 20.0
    meaningful_order_notional: float = 10000.0
    max_pending_seconds: int = 600
    cooldown_cycles: int = 1
    stop_loss_pct: float = 1.5
    partial_take_profit_pct: float = 2.0
    trailing_stop_pct: float = 1.0
    partial_sell_ratio: float = 0.5
    max_total_exposure_pct: float = 60.0


class FileConfig(BaseModel):
    app: AppConfig = Field(default_factory=AppConfig)
    trading: TradingConfig = Field(default_factory=TradingConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    auto_trade: AutoTradeConfig = Field(default_factory=AutoTradeConfig)
    strategies: dict[str, StrategyToggleConfig] = Field(default_factory=dict)


class Settings(BaseSettings):
    config_path: str = "config/app.yml"
    app_name: str = "investment-bot"
    environment: str = "local"
    trading_mode: str = "paper"
    base_currency: str = "KRW"
    symbols: list[str] = Field(default_factory=lambda: ["BTC/KRW"])
    starting_cash: float = 10_000_000
    min_order_notional: float = 0.0
    max_consecutive_buys: int = 3
    max_symbol_exposure_pct: float = 25.0
    ledger_path: str = "data/paper_ledger.json"
    candle_store_path: str = "data/candles.json"
    run_history_path: str = "data/run_history.json"
    upbit_access_key: str = Field(default="", validation_alias="UPBIT_ACCESS_KEY")
    upbit_secret_key: str = Field(default="", validation_alias="UPBIT_SECRET_KEY")
    live_mode: str = Field(default="shadow", validation_alias="INVESTMENT_BOT_LIVE_MODE")
    confirm_live_trading: bool = False
    trading_fee_pct: float = 0.05
    slippage_pct: float = 0.05
    max_risk_per_trade_pct: float = 1.0
    max_daily_loss_pct: float = 3.0
    max_drawdown_pct: float = 10.0
    auto_trade_enabled: bool = False
    auto_trade_symbol: str = "BTC/KRW"
    auto_trade_strategy_name: str = "trend_following"
    auto_trade_timeframe: str = "1h"
    auto_trade_limit: int = 5
    auto_trade_interval_seconds: int = 300
    auto_trade_min_krw_balance: float = 15000.0
    auto_trade_target_allocation_pct: float = 20.0
    auto_trade_meaningful_order_notional: float = 10000.0
    auto_trade_max_pending_seconds: int = 600
    auto_trade_cooldown_cycles: int = 1
    auto_trade_stop_loss_pct: float = 1.5
    auto_trade_partial_take_profit_pct: float = 2.0
    auto_trade_trailing_stop_pct: float = 1.0
    auto_trade_partial_sell_ratio: float = 0.5
    auto_trade_max_total_exposure_pct: float = 60.0
    enabled_strategies: list[str] = Field(default_factory=lambda: ["trend_following", "mean_reversion", "dca"])

    model_config = SettingsConfigDict(env_prefix="INVESTMENT_BOT_", env_file=".env", extra="ignore")


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
        starting_cash=file_config.trading.starting_cash,
        min_order_notional=file_config.trading.min_order_notional,
        max_consecutive_buys=file_config.trading.max_consecutive_buys,
        max_symbol_exposure_pct=file_config.trading.max_symbol_exposure_pct,
        ledger_path=raw_settings.ledger_path,
        candle_store_path=raw_settings.candle_store_path,
        run_history_path=raw_settings.run_history_path,
        upbit_access_key=raw_settings.upbit_access_key,
        upbit_secret_key=raw_settings.upbit_secret_key,
        live_mode=raw_settings.live_mode,
        confirm_live_trading=raw_settings.confirm_live_trading,
        trading_fee_pct=raw_settings.trading_fee_pct,
        slippage_pct=raw_settings.slippage_pct,
        max_risk_per_trade_pct=file_config.risk.max_risk_per_trade_pct,
        max_daily_loss_pct=file_config.risk.max_daily_loss_pct,
        max_drawdown_pct=file_config.risk.max_drawdown_pct,
        auto_trade_enabled=file_config.auto_trade.enabled,
        auto_trade_symbol=file_config.auto_trade.symbol,
        auto_trade_strategy_name=file_config.auto_trade.strategy_name,
        auto_trade_timeframe=file_config.auto_trade.timeframe,
        auto_trade_limit=file_config.auto_trade.limit,
        auto_trade_interval_seconds=file_config.auto_trade.interval_seconds,
        auto_trade_min_krw_balance=file_config.auto_trade.min_krw_balance,
        auto_trade_target_allocation_pct=file_config.auto_trade.target_allocation_pct,
        auto_trade_meaningful_order_notional=file_config.auto_trade.meaningful_order_notional,
        auto_trade_max_pending_seconds=file_config.auto_trade.max_pending_seconds,
        auto_trade_cooldown_cycles=file_config.auto_trade.cooldown_cycles,
        auto_trade_stop_loss_pct=file_config.auto_trade.stop_loss_pct,
        auto_trade_partial_take_profit_pct=file_config.auto_trade.partial_take_profit_pct,
        auto_trade_trailing_stop_pct=file_config.auto_trade.trailing_stop_pct,
        auto_trade_partial_sell_ratio=file_config.auto_trade.partial_sell_ratio,
        enabled_strategies=enabled_strategies,
    )
