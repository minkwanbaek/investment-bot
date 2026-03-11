from investment_bot.models.order import PaperOrder
from investment_bot.models.portfolio import PortfolioSnapshot, PositionSnapshot
from investment_bot.services.ledger_store import LedgerStore


class PaperBroker:
    def __init__(
        self,
        starting_cash: float = 10_000_000,
        ledger_store: LedgerStore | None = None,
        trading_fee_pct: float = 0.05,
        slippage_pct: float = 0.05,
        min_order_notional: float = 5_000,
        max_consecutive_buys: int = 3,
        max_symbol_exposure_pct: float = 25.0,
    ):
        self.starting_cash = starting_cash
        self.cash_balance = starting_cash
        self.orders: list[PaperOrder] = []
        self.positions: dict[str, dict] = {}
        self.last_prices: dict[str, float] = {}
        self.total_realized_pnl = 0.0
        self.trading_fee_pct = trading_fee_pct
        self.slippage_pct = slippage_pct
        self.min_order_notional = min_order_notional
        self.max_consecutive_buys = max_consecutive_buys
        self.max_symbol_exposure_pct = max_symbol_exposure_pct
        self.consecutive_buys = 0
        self.ledger_store = ledger_store
        self._load_state()

    def _load_state(self) -> None:
        if not self.ledger_store:
            return
        payload = self.ledger_store.load()
        if not payload:
            return
        self.cash_balance = payload.get("cash_balance", self.starting_cash)
        self.positions = payload.get("positions", {})
        self.last_prices = payload.get("last_prices", {})
        self.total_realized_pnl = payload.get("total_realized_pnl", 0.0)
        self.consecutive_buys = payload.get("consecutive_buys", 0)
        self.orders = [PaperOrder.model_validate(order) for order in payload.get("orders", [])]

    def _persist_state(self) -> None:
        if not self.ledger_store:
            return
        self.ledger_store.save(
            {
                "starting_cash": self.starting_cash,
                "cash_balance": self.cash_balance,
                "positions": self.positions,
                "last_prices": self.last_prices,
                "total_realized_pnl": self.total_realized_pnl,
                "consecutive_buys": self.consecutive_buys,
                "orders": [order.model_dump() for order in self.orders],
                "portfolio": self.portfolio_snapshot(),
            }
        )

    def submit(self, reviewed_signal: dict, execution_price: float) -> dict:
        action = reviewed_signal["action"]
        approved_size = reviewed_signal["size_scale"]
        symbol = reviewed_signal.get("symbol", "BTC/KRW")
        requested_price = execution_price
        slippage_multiplier = 1 + (self.slippage_pct / 100) if action == "buy" else 1 - (self.slippage_pct / 100)
        executed_price = round(requested_price * slippage_multiplier, 4)
        notional_value = round(approved_size * executed_price, 4)
        fee_paid = round(notional_value * (self.trading_fee_pct / 100), 4)
        total_buy_cost = round(notional_value + fee_paid, 4)

        if action == "buy" and notional_value < self.min_order_notional:
            return {"status": "rejected", "reason": "below_min_order_notional", "min_order_notional": self.min_order_notional}
        if action == "buy" and self.consecutive_buys >= self.max_consecutive_buys:
            return {"status": "rejected", "reason": "max_consecutive_buys_reached", "max_consecutive_buys": self.max_consecutive_buys}
        if action == "buy" and total_buy_cost > self.cash_balance:
            return {"status": "rejected", "reason": "insufficient_cash", "cash_balance": self.cash_balance}
        if action == "buy":
            current_position_value = self.positions.get(symbol, {}).get("quantity", 0.0) * requested_price
            max_symbol_exposure_value = self.starting_cash * (self.max_symbol_exposure_pct / 100)
            if current_position_value + notional_value > max_symbol_exposure_value:
                return {
                    "status": "rejected",
                    "reason": "max_symbol_exposure_reached",
                    "max_symbol_exposure_pct": self.max_symbol_exposure_pct,
                }

        order = PaperOrder(
            strategy_name=reviewed_signal["strategy_name"],
            symbol=symbol,
            action=action,
            confidence=reviewed_signal["confidence"],
            requested_size=reviewed_signal["confidence"],
            approved_size=approved_size,
            requested_price=requested_price,
            execution_price=executed_price,
            slippage_pct=self.slippage_pct,
            fee_pct=self.trading_fee_pct,
            fee_paid=fee_paid,
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
            total_cost = (position["quantity"] * position["average_price"]) + notional_value + fee_paid
            new_quantity = position["quantity"] + approved_size
            position["quantity"] = round(new_quantity, 4)
            position["average_price"] = round(total_cost / new_quantity, 4) if new_quantity else 0.0
            self.cash_balance = round(self.cash_balance - total_buy_cost, 4)
            self.consecutive_buys += 1
        elif action == "sell":
            sell_quantity = min(approved_size, position["quantity"])
            if sell_quantity <= 0:
                return {"status": "rejected", "reason": "no_position_to_sell", "symbol": symbol}
            realized_pnl = ((executed_price - position["average_price"]) * sell_quantity) - fee_paid
            position["quantity"] = round(position["quantity"] - sell_quantity, 4)
            if position["quantity"] == 0:
                position["average_price"] = 0.0
            position["realized_pnl"] = round(position["realized_pnl"] + realized_pnl, 4)
            self.total_realized_pnl = round(self.total_realized_pnl + realized_pnl, 4)
            self.cash_balance = round(self.cash_balance + (sell_quantity * executed_price) - fee_paid, 4)
            self.consecutive_buys = 0

        self._persist_state()
        return {"status": "recorded", "order": order.model_dump()}

    def mark_price(self, symbol: str, market_price: float) -> None:
        self.last_prices[symbol] = market_price
        self._persist_state()

    def reset(self) -> dict:
        self.cash_balance = self.starting_cash
        self.orders = []
        self.positions = {}
        self.last_prices = {}
        self.total_realized_pnl = 0.0
        self.consecutive_buys = 0
        self._persist_state()
        return self.portfolio_snapshot()

    def export_state(self) -> dict:
        return {
            "starting_cash": self.starting_cash,
            "cash_balance": self.cash_balance,
            "positions": self.positions,
            "last_prices": self.last_prices,
            "total_realized_pnl": self.total_realized_pnl,
            "consecutive_buys": self.consecutive_buys,
            "orders": [order.model_dump() for order in self.orders],
            "portfolio": self.portfolio_snapshot(),
        }

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
