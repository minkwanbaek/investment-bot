from investment_bot.models.order import PaperOrder


class PaperBroker:
    def __init__(self, starting_cash: float = 10_000_000):
        self.starting_cash = starting_cash
        self.cash_balance = starting_cash
        self.orders: list[PaperOrder] = []
        self.positions: dict[str, float] = {}

    def submit(self, reviewed_signal: dict) -> dict:
        action = reviewed_signal["action"]
        approved_size = reviewed_signal["size_scale"]
        symbol = reviewed_signal.get("symbol", "BTC/KRW")

        order = PaperOrder(
            strategy_name=reviewed_signal["strategy_name"],
            symbol=symbol,
            action=action,
            confidence=reviewed_signal["confidence"],
            requested_size=reviewed_signal["confidence"],
            approved_size=approved_size,
            reason=reviewed_signal["reason"],
        )
        self.orders.append(order)

        signed_size = approved_size if action == "buy" else -approved_size
        self.positions[symbol] = round(self.positions.get(symbol, 0.0) + signed_size, 4)

        return {"status": "recorded", "order": order.model_dump()}

    def portfolio_snapshot(self) -> dict:
        return {
            "cash_balance": self.cash_balance,
            "starting_cash": self.starting_cash,
            "positions": self.positions,
            "order_count": len(self.orders),
        }
