from investment_bot.models.signal import TradeSignal


class RiskController:
    def __init__(self, max_confidence_position_scale: float = 1.0):
        self.max_confidence_position_scale = max_confidence_position_scale

    def review(self, signal: TradeSignal) -> dict:
        approved = signal.action != "hold"
        size_scale = round(signal.confidence * self.max_confidence_position_scale, 4)
        return {
            "approved": approved,
            "strategy_name": signal.strategy_name,
            "symbol": signal.symbol,
            "action": signal.action,
            "confidence": signal.confidence,
            "size_scale": size_scale if approved else 0.0,
            "reason": signal.reason,
        }
