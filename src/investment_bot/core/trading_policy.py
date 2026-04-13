from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from investment_bot.core.settings import Settings


REGIME_TREND_UP = "trend_up"
REGIME_TREND_DOWN = "trend_down"
REGIME_SIDEWAYS = "sideways"
REGIME_UNCERTAIN = "uncertain"


@dataclass(frozen=True)
class TradingPolicySnapshot:
    max_consecutive_buys: int
    trend_strategy_allowed_regimes: tuple[str, ...]
    range_strategy_allowed_regimes: tuple[str, ...]
    uncertain_block_enabled: bool
    sideway_filter_enabled: bool
    sideway_filter_trend_gap_threshold: float
    sideway_filter_range_threshold: float
    sideway_filter_volatility_block_on_low: bool
    sideway_filter_breakout_exception_enabled: bool
    sideway_filter_breakout_exception_momentum_min: float
    sideway_filter_breakout_exception_trend_gap_ratio: float
    sideway_filter_breakout_exception_allow_bearish_higher_tf: bool
    sideway_filter_breakout_exception_allow_low_volatility: bool
    high_volatility_defense_enabled: bool
    volatility_size_multipliers: dict[str, float]
    meaningful_order_notional: float
    min_managed_position_notional: float
    max_symbol_exposure_pct: float
    max_total_exposure_pct: float
    target_allocation_pct: float


@dataclass(frozen=True)
class PolicyObservation:
    policy_name: str
    policy_value: Any
    current_state: Any
    block_reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "policy_name": self.policy_name,
            "policy_value": self.policy_value,
            "current_state": self.current_state,
            "block_reason": self.block_reason,
        }


class TradingPolicy:
    def __init__(self, settings: Settings):
        self._settings = settings

    @property
    def snapshot(self) -> TradingPolicySnapshot:
        return TradingPolicySnapshot(
            max_consecutive_buys=self._settings.max_consecutive_buys,
            trend_strategy_allowed_regimes=tuple(self._normalize_regime_list(self._settings.trend_strategy_allowed_regimes)),
            range_strategy_allowed_regimes=tuple(self._normalize_regime_list(self._settings.range_strategy_allowed_regimes)),
            uncertain_block_enabled=self._settings.uncertain_block_enabled,
            sideway_filter_enabled=self._settings.sideway_filter_enabled,
            sideway_filter_trend_gap_threshold=self._settings.sideway_filter_trend_gap_threshold,
            sideway_filter_range_threshold=self._settings.sideway_filter_range_threshold,
            sideway_filter_volatility_block_on_low=self._settings.sideway_filter_volatility_block_on_low,
            sideway_filter_breakout_exception_enabled=self._settings.sideway_filter_breakout_exception_enabled,
            sideway_filter_breakout_exception_momentum_min=self._settings.sideway_filter_breakout_exception_momentum_min,
            sideway_filter_breakout_exception_trend_gap_ratio=self._settings.sideway_filter_breakout_exception_trend_gap_ratio,
            sideway_filter_breakout_exception_allow_bearish_higher_tf=self._settings.sideway_filter_breakout_exception_allow_bearish_higher_tf,
            sideway_filter_breakout_exception_allow_low_volatility=self._settings.sideway_filter_breakout_exception_allow_low_volatility,
            high_volatility_defense_enabled=self._settings.high_volatility_defense_enabled,
            volatility_size_multipliers=dict(self._settings.volatility_size_multipliers),
            meaningful_order_notional=self._settings.auto_trade_meaningful_order_notional,
            min_managed_position_notional=self._settings.auto_trade_min_managed_position_notional,
            max_symbol_exposure_pct=self._settings.max_symbol_exposure_pct,
            max_total_exposure_pct=self._settings.auto_trade_max_total_exposure_pct,
            target_allocation_pct=self._settings.auto_trade_target_allocation_pct,
        )

    def normalize_regime(self, regime: str | None) -> str:
        mapping = {
            "uptrend": REGIME_TREND_UP,
            "trend_up": REGIME_TREND_UP,
            "downtrend": REGIME_TREND_DOWN,
            "trend_down": REGIME_TREND_DOWN,
            "ranging": REGIME_SIDEWAYS,
            "sideways": REGIME_SIDEWAYS,
            "mixed": REGIME_UNCERTAIN,
            "unknown": REGIME_UNCERTAIN,
            "uncertain": REGIME_UNCERTAIN,
        }
        return mapping.get(str(regime or "").strip().lower(), REGIME_UNCERTAIN)

    def normalize_market_info(self, market_info: dict[str, Any]) -> dict[str, Any]:
        return {**market_info, "regime": self.normalize_regime(market_info.get("regime"))}

    def observe(self, *, policy_name: str, policy_value: Any, current_state: Any, block_reason: str) -> dict[str, Any]:
        return PolicyObservation(
            policy_name=policy_name,
            policy_value=policy_value,
            current_state=current_state,
            block_reason=block_reason,
        ).as_dict()

    def _normalize_regime_list(self, regimes: list[str]) -> list[str]:
        seen: list[str] = []
        for regime in regimes:
            normalized = self.normalize_regime(regime)
            if normalized not in seen:
                seen.append(normalized)
        return seen


def build_trading_policy(settings: Settings) -> TradingPolicy:
    return TradingPolicy(settings)
