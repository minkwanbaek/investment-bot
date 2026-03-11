from investment_bot.models.order import PaperOrder
from investment_bot.models.portfolio import PortfolioSnapshot, PositionSnapshot


class PaperBroker:
    def __init__(self, starting_cash: float = 10_000_000):
        self.starting_cash = starting_cash
        self.cash_balance = starting_cash
        self.orders: list[PaperOrder] = []
        self.positions: dict[str, dict] = {}
        self.last_prices: dict[str, float] = {}
        self.total_realized_pnl = 0.0

    def submit(self, reviewed_signal: dict, execution_price: float) -> dict:
        action = reviewed_signal["action"]
        approved_size = reviewed_signal["size_scale"]
        symbol = reviewed_signal.get("symbol", "BTC/KRW")
        notional_value = round(approved_size * execution_price, 4)

        order = PaperOrder(
            strategy_name=reviewed_signal["strategy_name"],
            symbol=symbol,
            action=action,
            confidence=reviewed_signal["confidence"],
            requested_size=reviewed_signal["confidence"],
            approved_size=approved_size,
            execution_price=execution_price,
            notional_value=notional_value,
            reason=reviewed_signal["reason"],
        )
        self.orders.append(order)
        self.last_prices[symbol] = execution_price

        position = self.positions.setdefault(
            symbol,
            {"quantity": 0.0, "average_price": 0.0, "realized_pnl": 0.0},
        )

        if action == "buy":
            total_cost = (position["quantity"] * position["average_price"]) + notional_value
            new_quantity = position["quantity"] + approved_size
            position["quantity"] = round(new_quantity, 4)
            position["average_price"] = round(total_cost / new_quantity, 4) if new_quantity else 0.0
            self.cash_balance = round(self.cash_balance - notional_value, 4)
        elif action == "sell":
            sell_quantity = min(approved_size, position["quantity"])
            realized_pnl = (execution_price - position["average_price"]) * sell_quantity
            position["quantity"] = round(position["quantity"] - sell_quantity, 4)
            if position["quantity"] == 0:
                position["average_price"] = 0.0
            position["realized_pnl"] = round(position["realized_pnl"] + realized_pnl, 4)
            self.total_realized_pnl = round(self.total_realized_pnl + realized_pnl, 4)
            self.cash_balance = round(self.cash_balance + (sell_quantity * execution_price), 4)

        return {"status": "recorded", "order": order.model_dump()}

    def mark_price(self, symbol: str, market_price: float) -> None:
        self.last_prices[symbol] = market_price

    def portfolio_snapshot(self) -> dict:
        snapshots: dict[str, PositionSnapshot] = {}
        total_unrealized_pnl = 0.0

        for symbol, position in self.positions.items():
            market_price = self.last_prices.get(symbol, position["average_price"])
            quantity = position["quantity"]
            cost_basis = round(quantity * position["average_price"], 4)
            market_value = round(quantity * market_price, 4)
            unrealized_pnl = round(market_value - cost_basis, 4)
            total_unrealized_pnl += unrealized_pnl
            snapshots[symbol] = PositionSnapshot(
                symbol=symbol,
                quantity=quantity,
                average_price=position["average_price"],
                market_price=market_price,
                market_value=market_value,
                cost_basis=cost_basis,
                unrealized_pnl=unrealized_pnl,
                realized_pnl=position["realized_pnl"],
            )

        total_equity = round(self.cash_balance + sum(item.market_value for item in snapshots.values()), 4)
        snapshot = PortfolioSnapshot(
            cash_balance=self.cash_balance,
            starting_cash=self.starting_cash,
            positions=snapshots,
            order_count=len(self.orders),
            total_equity=total_equity,
            total_realized_pnl=self.total_realized_pnl,
            total_unrealized_pnl=round(total_unrealized_pnl, 4),
        )
        return snapshot.model_dump()
