import math
from datetime import datetime, timezone
from uuid import uuid4

from investment_bot.core.settings import get_settings
from investment_bot.features.exit.application.evaluator import ExitEvaluator
from investment_bot.features.exit.domain.models import MarketSnapshot, PositionSnapshot as ExitPositionSnapshot
from investment_bot.core.trading_policy import PolicyObservation

from investment_bot.models.order import PaperOrder
from investment_bot.models.portfolio import PortfolioSnapshot, PositionSnapshot
from investment_bot.models.trade_log import TradeLogSchema
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
        self.min_meaningful_position_notional = max(min_order_notional, 5000)
        self.consecutive_buys = 0
        self.consecutive_buys_by_symbol: dict[str, int] = {}
        self.losing_streak = 0
        self.ledger_store = ledger_store
        self._load_state()

    def _round_qty(self, quantity: float) -> float:
        return round(quantity, 8)

    def _cleanup_dust_position(self, symbol: str, market_price: float | None = None) -> None:
        position = self.positions.get(symbol)
        if not position:
            return
        qty = max(position.get('quantity', 0.0), 0.0)
        if qty <= 0:
            position['quantity'] = 0.0
            position['average_price'] = 0.0
            return
        ref_price = market_price if market_price is not None else self.last_prices.get(symbol, position.get('average_price', 0.0))
        notional = qty * max(ref_price or 0.0, 0.0)
        # Only cleanup dust if position was explicitly closed (qty near zero) or notional is truly negligible
        # Do not cleanup small but intentional crypto positions
        if qty < 1e-6 or (notional < 100 and qty < 0.001):
            position['quantity'] = 0.0
            position['average_price'] = 0.0

    def _current_total_equity(self, symbol: str | None = None, market_price: float | None = None) -> float:
        total_position_value = 0.0
        for position_symbol, position in self.positions.items():
            qty = max((position or {}).get("quantity", 0.0), 0.0)
            if position_symbol == symbol and market_price is not None:
                ref_price = market_price
            else:
                ref_price = self.last_prices.get(position_symbol, (position or {}).get("average_price", 0.0))
            total_position_value += qty * max(ref_price or 0.0, 0.0)
        return round(self.cash_balance + total_position_value, 4)

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
        self.consecutive_buys_by_symbol = payload.get("consecutive_buys_by_symbol", {})
        self.losing_streak = payload.get("losing_streak", 0)
        self.orders = [PaperOrder.model_validate(order) for order in payload.get("orders", [])]
        meaningful_symbols = []
        for symbol, position in self.positions.items():
            qty = max((position or {}).get("quantity", 0.0), 0.0)
            avg = max((position or {}).get("average_price", 0.0), 0.0)
            if qty * avg >= self.min_meaningful_position_notional:
                meaningful_symbols.append(symbol)
        if len(meaningful_symbols) == 0:
            self.consecutive_buys = 0
            self.consecutive_buys_by_symbol = {}
        elif not self.consecutive_buys_by_symbol and len(meaningful_symbols) == 1 and self.consecutive_buys > 0:
            self.consecutive_buys_by_symbol = {meaningful_symbols[0]: self.consecutive_buys}

    def _persist_state(self) -> None:
        if not self.ledger_store:
            return
        existing = self.ledger_store.load() or {}
        self.ledger_store.save(
            {
                **existing,
                "starting_cash": self.starting_cash,
                "cash_balance": self.cash_balance,
                "positions": self.positions,
                "last_prices": self.last_prices,
                "total_realized_pnl": self.total_realized_pnl,
                "consecutive_buys": self.consecutive_buys,
                "consecutive_buys_by_symbol": self.consecutive_buys_by_symbol,
                "losing_streak": self.losing_streak,
                "orders": [order.model_dump() for order in self.orders],
                "portfolio": self.portfolio_snapshot(),
            }
        )

    def sync_exchange_position(self, symbol: str, quantity: float, average_price: float, cash_balance: float | None = None) -> None:
        position = self.positions.setdefault(
            symbol,
            {
                "quantity": 0.0,
                "average_price": 0.0,
                "realized_pnl": 0.0,
                "opened_at": None,
                "stop_price": None,
                "tp1_price": None,
                "tp1_done": False,
                "trailing_active": False,
                "trailing_stop_price": None,
            },
        )
        position["quantity"] = self._round_qty(max(quantity, 0.0))
        position["average_price"] = round(max(average_price, 0.0), 4) if position["quantity"] > 0 else 0.0
        if cash_balance is not None:
            self.cash_balance = round(max(cash_balance, 0.0), 4)
        self._persist_state()

    def submit(self, reviewed_signal: dict, execution_price: float, now: datetime | None = None) -> dict:
        now = now or datetime.now(timezone.utc)
        action = reviewed_signal["action"]
        approved_size = reviewed_signal["size_scale"]
        symbol = reviewed_signal.get("symbol", "BTC/KRW")
        requested_price = execution_price
        slippage_multiplier = 1 + (self.slippage_pct / 100) if action == "buy" else 1 - (self.slippage_pct / 100)
        executed_price = round(requested_price * slippage_multiplier, 4)
        effective_size = approved_size
        if action == "sell":
            existing_position = self.positions.get(symbol) or {}
            effective_size = min(approved_size, max(existing_position.get("quantity", 0.0), 0.0))
        notional_value = round(effective_size * executed_price, 4)
        fee_paid = round(notional_value * (self.trading_fee_pct / 100), 4)
        total_buy_cost = round(notional_value + fee_paid, 4)

        if action == "buy" and notional_value < self.min_order_notional:
            return {
                "status": "rejected",
                "reason": "below_min_order_notional",
                "min_order_notional": self.min_order_notional,
                "notional": notional_value,
                "action": action,
                "symbol": symbol,
            }
        if action == "sell" and notional_value < self.min_order_notional:
            return {
                "status": "rejected",
                "reason": "below_min_order_notional",
                "min_order_notional": self.min_order_notional,
                "notional": notional_value,
                "action": action,
                "symbol": symbol,
            }
        symbol_consecutive_buys = int(self.consecutive_buys_by_symbol.get(symbol, 0) or 0)
        if action == "buy" and symbol_consecutive_buys >= self.max_consecutive_buys:
            return {
                "status": "rejected",
                "reason": "max_consecutive_buys_reached",
                "max_consecutive_buys": self.max_consecutive_buys,
                "policy": PolicyObservation(
                    policy_name="max_consecutive_buys",
                    policy_value=self.max_consecutive_buys,
                    current_state=symbol_consecutive_buys,
                    block_reason="max_consecutive_buys_reached",
                ).as_dict(),
            }
        if action == "buy" and total_buy_cost > self.cash_balance:
            return {
                "status": "rejected",
                "reason": "insufficient_cash",
                "cash_balance": self.cash_balance,
                "required": total_buy_cost,
                "action": action,
                "symbol": symbol,
            }
        if action == "buy":
            current_position_value = self.positions.get(symbol, {}).get("quantity", 0.0) * requested_price
            max_symbol_exposure_value = self._current_total_equity(symbol, requested_price) * (self.max_symbol_exposure_pct / 100)
            if current_position_value + notional_value > max_symbol_exposure_value:
                return {
                    "status": "rejected",
                    "reason": "max_symbol_exposure_reached",
                    "max_symbol_exposure_pct": self.max_symbol_exposure_pct,
                    "policy": PolicyObservation(
                        policy_name="max_symbol_exposure_pct",
                        policy_value=self.max_symbol_exposure_pct,
                        current_state=round(((current_position_value + notional_value) / self.starting_cash) * 100, 4) if self.starting_cash > 0 else None,
                        block_reason="max_symbol_exposure_reached",
                    ).as_dict(),
                }

        order = PaperOrder(
            strategy_name=reviewed_signal["strategy_name"],
            symbol=symbol,
            action=action,
            confidence=reviewed_signal["confidence"],
            requested_size=reviewed_signal["confidence"],
            approved_size=effective_size,
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
            {
                "quantity": 0.0,
                "average_price": 0.0,
                "realized_pnl": 0.0,
                "opened_at": None,
                "stop_price": None,
                "tp1_price": None,
                "tp1_done": False,
                "trailing_active": False,
                "trailing_stop_price": None,
            },
        )

        if action == "buy":
            total_cost = (position["quantity"] * position["average_price"]) + notional_value + fee_paid
            new_quantity = position["quantity"] + approved_size
            position["quantity"] = self._round_qty(new_quantity)
            position["average_price"] = round(total_cost / new_quantity, 4) if new_quantity else 0.0
            position["opened_at"] = now.isoformat().replace("+00:00", "Z")
            settings = get_settings()
            if settings.atr_stop_enabled:
                stop_distance = executed_price * 0.01 * settings.stop_atr_multiplier
                position["stop_price"] = round(max(executed_price - stop_distance, 0.0), 4)
            if settings.partial_take_profit_enabled:
                position["tp1_price"] = round(executed_price * (1 + settings.tp1_ratio), 4)
                position["tp1_done"] = False
            position["trailing_active"] = False
            position["trailing_stop_price"] = None
            self.cash_balance = round(self.cash_balance - total_buy_cost, 4)
            self._cleanup_dust_position(symbol, executed_price)
            self.consecutive_buys_by_symbol[symbol] = symbol_consecutive_buys + 1
            self.consecutive_buys = max(self.consecutive_buys_by_symbol.values(), default=0)
            if self.ledger_store:
                self.ledger_store.append_trade_log_entry(
                    TradeLogSchema(
                        trade_id=str(uuid4()),
                        strategy_version=reviewed_signal.get("strategy_version"),
                        symbol=symbol,
                        side="buy",
                        entry_time=now,
                        entry_price=executed_price,
                        quantity=approved_size,
                        entry_reason=reviewed_signal["reason"],
                        market_regime=reviewed_signal.get("market_regime"),
                        volatility_state=reviewed_signal.get("volatility_state"),
                        higher_tf_bias=reviewed_signal.get("higher_tf_bias"),
                    )
                )
        elif action == "sell":
            # Upbit 최소 주문 금액 체크 (5,000 원)
            current_position_value = position["quantity"] * executed_price
            if current_position_value < self.min_order_notional:
                return {
                    "status": "rejected",
                    "reason": "below_min_order_notional",
                    "min_order_notional": self.min_order_notional,
                    "position_value": current_position_value,
                    "action": action,
                    "symbol": symbol,
                }
            
            sell_quantity = min(effective_size, position["quantity"])
            if sell_quantity <= 0:
                return {
                    "status": "rejected",
                    "reason": "no_position_to_sell",
                    "symbol": symbol,
                    "action": action,
                    "position_qty": position["quantity"],
                }
            average_price_before_sell = position["average_price"]
            realized_pnl = ((executed_price - average_price_before_sell) * sell_quantity) - fee_paid
            position["quantity"] = self._round_qty(position["quantity"] - sell_quantity)
            if position["quantity"] <= 0:
                position["quantity"] = 0.0
                position["average_price"] = 0.0
            self._cleanup_dust_position(symbol, executed_price)
            if position["quantity"] <= 0:
                position["average_price"] = 0.0
            position["realized_pnl"] = round(position["realized_pnl"] + realized_pnl, 4)
            if reviewed_signal.get("force_exit") and "partial_take_profit" in str(reviewed_signal.get("reason", "")):
                position["tp1_done"] = True
            self.total_realized_pnl = round(self.total_realized_pnl + realized_pnl, 4)
            self.cash_balance = round(self.cash_balance + (sell_quantity * executed_price) - fee_paid, 4)
            self.consecutive_buys_by_symbol[symbol] = 0
            self.consecutive_buys = max(self.consecutive_buys_by_symbol.values(), default=0)
            self.losing_streak = self.losing_streak + 1 if realized_pnl < 0 else 0
            if self.ledger_store:
                self.ledger_store.update_latest_open_trade_log(
                    symbol=symbol,
                    side="buy",
                    updates={
                        "exit_time": now.isoformat().replace("+00:00", "Z"),
                        "exit_price": executed_price,
                        "gross_pnl": round((executed_price - average_price_before_sell) * sell_quantity, 4),
                        "net_pnl": round(realized_pnl, 4),
                        "pnl_pct": round(((executed_price - average_price_before_sell) / average_price_before_sell) * 100, 4) if average_price_before_sell > 0 else None,
                        "holding_seconds": 0,
                        "exit_reason": reviewed_signal["reason"],
                    },
                )

        self._persist_state()
        return {"status": "recorded", "order": order.model_dump()}

    def evaluate_exit_rules(self, symbol: str, market_price: float, now: datetime | None = None) -> dict:
        now = now or datetime.now(timezone.utc)
        position = self.positions.get(symbol)
        if not position or position.get("quantity", 0.0) <= 0:
            return {"status": "no_position"}

        opened_at = position.get("opened_at")
        if isinstance(opened_at, str):
            opened_at = datetime.fromisoformat(opened_at.replace("Z", "+00:00"))

        evaluator = ExitEvaluator.from_runtime(
            min_order_notional=self.min_order_notional,
            slippage_pct=self.slippage_pct,
        )
        decision = evaluator.evaluate_position_exit(
            ExitPositionSnapshot(
                symbol=symbol,
                quantity=float(position.get("quantity", 0.0) or 0.0),
                average_price=float(position.get("average_price", 0.0) or 0.0),
                opened_at=opened_at,
                trailing_active=bool(position.get("trailing_active", False)),
                trailing_stop_price=position.get("trailing_stop_price"),
                tp1_done=bool(position.get("tp1_done", False)),
                tp1_price=position.get("tp1_price"),
                stop_price=position.get("stop_price"),
            ),
            MarketSnapshot(latest_price=market_price, now=now),
        )
        for key, value in decision.metadata.get("position_updates", {}).items():
            position[key] = value
        return self._serialize_exit_decision(decision)

    def _serialize_exit_decision(self, decision) -> dict:
        if not decision.triggered:
            return {"status": "hold"}
        exit_reason = decision.exit_reason or decision.reason
        return {
            "status": "triggered",
            "action": "sell",
            "reason": exit_reason,
            "exit_reason": exit_reason,
            "exit_source": "broker",
            "exit_priority": self._exit_priority_value(decision.priority),
            "exit_priority_label": decision.priority,
            "size_scale": decision.quantity,
            "exit_size_scale": decision.quantity,
            "confidence": decision.confidence,
        }

    def _exit_priority_value(self, priority: str) -> int:
        priorities = {
            "hard_stop": 240,
            "protective": 230,
            "profit_take": 220,
            "soft_exit": 210,
            "none": 0,
        }
        return priorities.get(priority, 0)

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
        self.consecutive_buys_by_symbol = {}
        self.losing_streak = 0
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
            "consecutive_buys_by_symbol": self.consecutive_buys_by_symbol,
            "losing_streak": self.losing_streak,
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
