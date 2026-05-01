from datetime import datetime, timezone

from investment_bot.core.settings import get_settings
from investment_bot.core.trading_policy import build_trading_policy
from investment_bot.models.signal import TradeSignal


class RiskController:
    def __init__(self, max_confidence_position_scale: float = 1.0, min_order_notional: float = 0.0, base_entry_notional: float = 10000.0):
        self.max_confidence_position_scale = max_confidence_position_scale
        self.min_order_notional = min_order_notional
        self.base_entry_notional = base_entry_notional

    def review(self, signal: TradeSignal, cash_balance: float = 0.0, latest_price: float = 1.0) -> dict:
        approved = signal.action != "hold"
        position_value_budget = cash_balance * signal.confidence * self.max_confidence_position_scale
        block_reason = None

        now_hour = datetime.now(timezone.utc).hour
        signal_meta = getattr(signal, "meta", {}) if hasattr(signal, "meta") else {}
        market_regime = signal_meta.get("market_regime")
        volatility_state = signal_meta.get("volatility_state", "normal")
        higher_tf_bias = signal_meta.get("higher_tf_bias", "neutral")
        force_exit = bool(signal_meta.get("force_exit", False))
        side = signal.action

        settings = get_settings()
        policy = build_trading_policy(settings)

        if approved and not force_exit and settings.time_blacklist_filter_enabled and now_hour in set(settings.blocked_hours):
            approved = False
            block_reason = "blocked_time_window"

        if approved and not force_exit and settings.higher_tf_bias_filter_enabled:
            if side == "buy" and higher_tf_bias == "bearish":
                approved = False
                block_reason = "higher_tf_bias_mismatch"
            elif side == "sell" and higher_tf_bias == "bullish":
                approved = False
                block_reason = "higher_tf_bias_mismatch"

        if approved and signal.action == "buy":
            if signal.confidence >= 0.5 and cash_balance >= self.base_entry_notional:
                position_value_budget = max(position_value_budget, self.base_entry_notional)
            elif cash_balance >= self.min_order_notional:
                position_value_budget = max(position_value_budget, self.min_order_notional)

        if approved and signal.action == "buy":
            position_value_budget = min(position_value_budget, cash_balance)

        if approved and force_exit and signal.action == "sell":
            position_value_budget = latest_price

        allowed_risk = cash_balance * settings.risk_control_risk_per_trade_pct
        if not (approved and force_exit and signal.action == "sell"):
            position_value_budget = min(position_value_budget, max(allowed_risk * 10, self.min_order_notional))
            position_value_budget *= policy.snapshot.volatility_size_multipliers.get(volatility_state, 1.0)

        losing_streak = int(signal_meta.get("losing_streak", 0) or 0)
        risk_mode = "normal"
        if losing_streak >= settings.losing_streak_threshold_minimal:
            risk_mode = "minimal"
        elif losing_streak >= settings.losing_streak_threshold_reduced:
            risk_mode = "reduced"
        position_value_budget *= settings.risk_mode_multipliers.get(risk_mode, 1.0)

        if (
            approved
            and signal.action == "buy"
            and risk_mode == "normal"
            and 0 < position_value_budget < self.min_order_notional
            and cash_balance >= self.min_order_notional
        ):
            position_value_budget = self.min_order_notional

        size_scale = round((position_value_budget / latest_price), 8) if approved and latest_price > 0 else 0.0
        return {
            "approved": approved,
            "strategy_name": signal.strategy_name,
            "symbol": signal.symbol,
            "action": signal.action,
            "confidence": signal.confidence,
            "cash_balance": cash_balance,
            "latest_price": latest_price,
            "target_notional": round(position_value_budget, 4) if approved else 0.0,
            "size_scale": size_scale if approved else 0.0,
            "reason": signal.reason if block_reason is None else f"{signal.reason}; {block_reason}",
            "market_regime": market_regime,
            "volatility_state": volatility_state,
            "higher_tf_bias": higher_tf_bias,
            "risk_mode": risk_mode,
            "losing_streak": losing_streak,
            "force_exit": force_exit,
        }
