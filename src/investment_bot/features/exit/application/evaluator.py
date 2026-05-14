from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone

from investment_bot.core.settings import Settings, get_settings
from investment_bot.features.exit.domain.models import ExitDecision, LiveExitOverrideDecision, MarketSnapshot, PositionSnapshot


@dataclass
class ExitEvaluator:
    settings: Settings
    min_order_notional: float
    slippage_pct: float = 0.0

    @classmethod
    def from_runtime(cls, min_order_notional: float, slippage_pct: float = 0.0) -> "ExitEvaluator":
        return cls(settings=get_settings(), min_order_notional=min_order_notional, slippage_pct=slippage_pct)

    def evaluate_position_exit(self, position: PositionSnapshot, market: MarketSnapshot) -> ExitDecision:
        latest_price = float(market.latest_price or 0.0)
        if position.quantity <= 0:
            return ExitDecision(action="hold", priority="none", reason="no_position")
        if position.average_price <= 0:
            return ExitDecision(action="hold", priority="none", reason="invalid_position")
        if latest_price <= 0:
            return ExitDecision(action="hold", priority="none", reason="invalid_market_price")

        position_updates: dict = {}

        if (
            self.settings.partial_take_profit_enabled
            and not position.tp1_done
            and position.tp1_price
            and latest_price >= position.tp1_price
        ):
            sell_qty = round(position.quantity * self.settings.tp1_size_pct, 8)
            if sell_qty * latest_price < self.min_order_notional <= position.quantity * latest_price:
                min_executable_qty = self.min_order_notional / (latest_price * (1 - (self.slippage_pct / 100)))
                sell_qty = min(position.quantity, math.ceil(min_executable_qty * 100_000_000) / 100_000_000)
            remaining_qty = max(position.quantity - sell_qty, 0.0)
            if 0 < remaining_qty * latest_price < self.min_order_notional:
                sell_qty = position.quantity
            if self.settings.trailing_stop_enabled:
                position_updates["trailing_active"] = True
                trailing_stop = round(latest_price * (1 - self.settings.trailing_distance_ratio), 4)
                current = position.trailing_stop_price
                position_updates["trailing_stop_price"] = trailing_stop if current is None else max(current, trailing_stop)
            return ExitDecision(
                action="sell",
                priority="profit_take",
                reason="partial_take_profit",
                quantity=sell_qty,
                confidence=1.0,
                exit_reason="partial_take_profit",
                metadata={"position_updates": position_updates},
            )

        gain_ratio = (latest_price - position.average_price) / position.average_price
        trailing_active = position.trailing_active
        trailing_stop_price = position.trailing_stop_price

        if self.settings.trailing_stop_enabled and gain_ratio >= self.settings.trailing_activation_ratio:
            trailing_active = True
            trailing_stop = round(latest_price * (1 - self.settings.trailing_distance_ratio), 4)
            current = trailing_stop_price
            trailing_stop_price = trailing_stop if current is None else max(current, trailing_stop)
            position_updates["trailing_active"] = True
            position_updates["trailing_stop_price"] = trailing_stop_price

        if trailing_active and trailing_stop_price and latest_price <= trailing_stop_price:
            return ExitDecision(
                action="sell",
                priority="protective",
                reason="trailing_stop",
                quantity=position.quantity,
                confidence=1.0,
                exit_reason="trailing_stop",
                metadata={"position_updates": position_updates},
            )

        if position.stop_price and latest_price <= position.stop_price:
            return ExitDecision(
                action="sell",
                priority="hard_stop",
                reason="atr_stop",
                quantity=position.quantity,
                confidence=1.0,
                exit_reason="atr_stop",
                metadata={"position_updates": position_updates},
            )

        now = market.now or datetime.now(timezone.utc)
        if self.settings.timeout_exit_enabled and position.opened_at:
            holding_minutes = (now - position.opened_at).total_seconds() / 60
            if holding_minutes >= self.settings.max_holding_minutes and gain_ratio < self.settings.min_progress_pct:
                return ExitDecision(
                    action="sell",
                    priority="protective",
                    reason="timeout",
                    quantity=position.quantity,
                    confidence=1.0,
                    exit_reason="timeout",
                    metadata={"position_updates": position_updates},
                )

        if market.trend_reversal:
            return ExitDecision(
                action="sell",
                priority="soft_exit",
                reason="trend_reversal",
                quantity=position.quantity,
                confidence=0.8,
                exit_reason="trend_reversal",
                metadata={"position_updates": position_updates},
            )

        return ExitDecision(action="hold", priority="none", reason="hold", metadata={"position_updates": position_updates})

    def evaluate_strategy_exit(
        self,
        *,
        position: PositionSnapshot,
        market: MarketSnapshot,
        stop_loss_pct: float | None = None,
        take_profit_pct: float | None = None,
        managed_rebound_exit_threshold: float | None = None,
        managed_rebound_exit_reason: str | None = None,
    ) -> ExitDecision:
        latest_price = float(market.latest_price or 0.0)
        if position.quantity <= 0:
            return ExitDecision(action="hold", priority="none", reason="no_position")
        if position.average_price <= 0 or latest_price <= 0:
            return ExitDecision(action="hold", priority="none", reason="invalid_position_or_price")

        pnl_ratio = (latest_price - position.average_price) / position.average_price
        if stop_loss_pct is not None and pnl_ratio <= stop_loss_pct:
            return ExitDecision(
                action="sell",
                priority="hard_stop",
                reason=f"stop_loss: pnl={pnl_ratio*100:.2f}%",
                quantity=position.quantity,
                confidence=1.0,
                exit_reason="stop_loss",
                metadata={"pnl_pct": round(pnl_ratio * 100, 4)},
            )
        if take_profit_pct is not None and pnl_ratio >= take_profit_pct:
            return ExitDecision(
                action="sell",
                priority="profit_take",
                reason=f"take_profit: pnl={pnl_ratio*100:.2f}%",
                quantity=position.quantity,
                confidence=1.0,
                exit_reason="take_profit",
                metadata={"pnl_pct": round(pnl_ratio * 100, 4)},
            )
        if managed_rebound_exit_threshold is not None and pnl_ratio >= managed_rebound_exit_threshold:
            return ExitDecision(
                action="sell",
                priority="soft_exit",
                reason=f"managed_rebound_exit: pnl={pnl_ratio*100:.2f}%",
                quantity=position.quantity,
                confidence=0.6,
                exit_reason=managed_rebound_exit_reason or "managed_rebound_exit",
                metadata={"pnl_pct": round(pnl_ratio * 100, 4)},
            )
        if market.trend_reversal:
            return ExitDecision(
                action="sell",
                priority="soft_exit",
                reason=f"trend_reversal: pnl={pnl_ratio*100:.2f}%",
                quantity=position.quantity,
                confidence=0.8,
                exit_reason="trend_reversal",
                metadata={"pnl_pct": round(pnl_ratio * 100, 4)},
            )
        return ExitDecision(action="hold", priority="none", reason="hold")

    def evaluate_live_exit_override(
        self,
        *,
        balance: float,
        avg_buy_price: float,
        latest_price: float,
        peak_price: float | None,
    ) -> LiveExitOverrideDecision:
        if balance <= 0 or avg_buy_price <= 0 or latest_price <= 0:
            return LiveExitOverrideDecision(action="hold", next_peak_price=None)

        peak = latest_price if peak_price is None else max(float(peak_price), latest_price)
        pnl_pct = ((latest_price - avg_buy_price) / avg_buy_price) * 100
        peak_pnl_pct = ((peak - avg_buy_price) / avg_buy_price) * 100
        drawdown_from_peak_pct = ((peak - latest_price) / peak) * 100 if peak > 0 else 0.0

        if pnl_pct <= -self.settings.auto_trade_stop_loss_pct:
            return LiveExitOverrideDecision(
                action="sell",
                reason="stop_loss",
                sell_ratio=1.0,
                pnl_pct=round(pnl_pct, 4),
                drawdown_from_peak_pct=round(drawdown_from_peak_pct, 4),
                next_peak_price=peak,
            )

        if (
            peak_pnl_pct >= self.settings.auto_trade_partial_take_profit_pct
            and pnl_pct > 0
            and drawdown_from_peak_pct >= self.settings.auto_trade_trailing_stop_pct
        ):
            return LiveExitOverrideDecision(
                action="sell",
                reason="take_profit_trailing_stop",
                sell_ratio=self.settings.auto_trade_partial_sell_ratio,
                pnl_pct=round(pnl_pct, 4),
                drawdown_from_peak_pct=round(drawdown_from_peak_pct, 4),
                next_peak_price=peak,
            )

        return LiveExitOverrideDecision(
            action="hold",
            pnl_pct=round(pnl_pct, 4),
            drawdown_from_peak_pct=round(drawdown_from_peak_pct, 4),
            next_peak_price=peak,
        )
