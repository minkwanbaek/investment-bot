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


class RiskConfig(BaseModel):
    max_risk_per_trade_pct: float = 1.0
    max_daily_loss_pct: float = 3.0
    max_drawdown_pct: float = 10.0


class StrategyToggleConfig(BaseModel):
    enabled: bool = True


class FileConfig(BaseModel):
    app: AppConfig = Field(default_factory=AppConfig)
    trading: TradingConfig = Field(default_factory=TradingConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
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
    ledger_path: str = "data/paper_ledger.json"
    candle_store_path: str = "data/candles.json"
    run_history_path: str = "data/run_history.json"
    trading_fee_pct: float = 0.05
    slippage_pct: float = 0.05
    max_risk_per_trade_pct: float = 1.0
    max_daily_loss_pct: float = 3.0
    max_drawdown_pct: float = 10.0
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
        ledger_path=raw_settings.ledger_path,
        candle_store_path=raw_settings.candle_store_path,
        run_history_path=raw_settings.run_history_path,
        trading_fee_pct=raw_settings.trading_fee_pct,
        slippage_pct=raw_settings.slippage_pct,
        max_risk_per_trade_pct=file_config.risk.max_risk_per_trade_pct,
        max_daily_loss_pct=file_config.risk.max_daily_loss_pct,
        max_drawdown_pct=file_config.risk.max_drawdown_pct,
        enabled_strategies=enabled_strategies,
    )
