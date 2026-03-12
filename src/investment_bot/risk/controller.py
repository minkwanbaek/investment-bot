from investment_bot.models.signal import TradeSignal


class RiskController:
    def __init__(self, max_confidence_position_scale: float = 1.0, min_order_notional: float = 0.0):
        self.max_confidence_position_scale = max_confidence_position_scale
        self.min_order_notional = min_order_notional

    def review(self, signal: TradeSignal, cash_balance: float = 0.0, latest_price: float = 1.0) -> dict:
        approved = signal.action != "hold"
        position_value_budget = cash_balance * signal.confidence * self.max_confidence_position_scale

        if approved and signal.action == "buy" and cash_balance >= self.min_order_notional:
            position_value_budget = max(position_value_budget, self.min_order_notional)

        if approved and signal.action == "buy":
            position_value_budget = min(position_value_budget, cash_balance)

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
            "reason": signal.reason,
        }
