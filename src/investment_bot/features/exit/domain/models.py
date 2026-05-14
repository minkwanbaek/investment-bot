from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


ExitPriority = Literal["hard_stop", "protective", "profit_take", "soft_exit", "none"]
ExitAction = Literal["sell", "hold"]


@dataclass
class PositionSnapshot:
    symbol: str
    quantity: float
    average_price: float
    opened_at: datetime | None = None
    trailing_active: bool = False
    trailing_stop_price: float | None = None
    tp1_done: bool = False
    tp1_price: float | None = None
    stop_price: float | None = None


@dataclass
class MarketSnapshot:
    latest_price: float
    now: datetime | None = None
    regime: str | None = None
    volatility_state: str | None = None
    higher_tf_bias: str | None = None
    trend_reversal: bool = False


@dataclass
class ExitDecision:
    action: ExitAction
    priority: ExitPriority
    reason: str
    quantity: float = 0.0
    confidence: float = 0.0
    exit_reason: str | None = None
    metadata: dict = field(default_factory=dict)

    @property
    def triggered(self) -> bool:
        return self.action == "sell"


@dataclass
class LiveExitOverrideDecision:
    action: ExitAction
    reason: str | None = None
    sell_ratio: float = 0.0
    pnl_pct: float | None = None
    drawdown_from_peak_pct: float | None = None
    next_peak_price: float | None = None

    @property
    def triggered(self) -> bool:
        return self.action == "sell"
