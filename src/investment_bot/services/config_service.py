from dataclasses import dataclass

from investment_bot.core.settings import Settings
from investment_bot.strategies.registry import list_registered_strategies


@dataclass
class ConfigService:
    settings: Settings

    def validate(self) -> dict:
        issues: list[str] = []
        warnings: list[str] = []

        if self.settings.starting_cash <= 0:
            issues.append("starting_cash must be > 0")
        if self.settings.max_risk_per_trade_pct <= 0:
            issues.append("max_risk_per_trade_pct must be > 0")
        if self.settings.max_daily_loss_pct <= 0:
            issues.append("max_daily_loss_pct must be > 0")
        if self.settings.max_drawdown_pct <= 0:
            issues.append("max_drawdown_pct must be > 0")
        if not self.settings.symbols:
            issues.append("at least one trading symbol is required")

        registered = set(list_registered_strategies())
        unknown_enabled = [name for name in self.settings.enabled_strategies if name not in registered]
        if unknown_enabled:
            issues.append(f"unknown enabled strategies: {', '.join(sorted(unknown_enabled))}")
        if not self.settings.enabled_strategies:
            warnings.append("no strategies are enabled")
        if self.settings.live_mode not in {"paper", "shadow", "live"}:
            issues.append("live_mode must be one of: paper, shadow, live")
        if self.settings.live_mode == "live" and not self.settings.confirm_live_trading:
            warnings.append("live mode selected but confirm_live_trading is false")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "resolved": {
                "starting_cash": self.settings.starting_cash,
                "symbols": self.settings.symbols,
                "enabled_strategies": self.settings.enabled_strategies,
                "risk": {
                    "max_risk_per_trade_pct": self.settings.max_risk_per_trade_pct,
                    "max_daily_loss_pct": self.settings.max_daily_loss_pct,
                    "max_drawdown_pct": self.settings.max_drawdown_pct,
                },
                "live_mode": self.settings.live_mode,
                "confirm_live_trading": self.settings.confirm_live_trading,
                "auto_trade": {
                    "enabled": self.settings.auto_trade_enabled,
                    "symbol": self.settings.auto_trade_symbol,
                    "strategy_name": self.settings.auto_trade_strategy_name,
                    "interval_seconds": self.settings.auto_trade_interval_seconds,
                    "min_krw_balance": self.settings.auto_trade_min_krw_balance,
                    "target_allocation_pct": self.settings.auto_trade_target_allocation_pct,
                    "meaningful_order_notional": self.settings.auto_trade_meaningful_order_notional,
                    "max_pending_seconds": self.settings.auto_trade_max_pending_seconds,
                    "cooldown_cycles": self.settings.auto_trade_cooldown_cycles,
                    "stop_loss_pct": self.settings.auto_trade_stop_loss_pct,
                    "partial_take_profit_pct": self.settings.auto_trade_partial_take_profit_pct,
                    "trailing_stop_pct": self.settings.auto_trade_trailing_stop_pct,
                    "partial_sell_ratio": self.settings.auto_trade_partial_sell_ratio,
                    "max_total_exposure_pct": self.settings.auto_trade_max_total_exposure_pct,
                },
            },
        }
