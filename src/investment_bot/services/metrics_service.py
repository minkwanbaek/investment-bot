from dataclasses import dataclass


@dataclass
class MetricsService:
    def summarize_backtest(self, starting_cash: float, runs: list[dict], final_portfolio: dict) -> dict:
        total_steps = len(runs)
        approved_orders = sum(1 for run in runs if run["review"]["approved"])
        buy_signals = sum(1 for run in runs if run["signal"]["action"] == "buy")
        sell_signals = sum(1 for run in runs if run["signal"]["action"] == "sell")
        hold_signals = sum(1 for run in runs if run["signal"]["action"] == "hold")

        equity_curve = [run["portfolio"]["total_equity"] for run in runs]
        ending_equity = final_portfolio["total_equity"]
        net_pnl = round(ending_equity - starting_cash, 4)
        return_pct = round((net_pnl / starting_cash) * 100, 4) if starting_cash else 0.0
        max_equity = starting_cash
        max_drawdown_pct = 0.0
        for equity in equity_curve:
            max_equity = max(max_equity, equity)
            drawdown_pct = ((max_equity - equity) / max_equity * 100) if max_equity else 0.0
            max_drawdown_pct = max(max_drawdown_pct, drawdown_pct)

        return {
            "total_steps": total_steps,
            "approved_orders": approved_orders,
            "buy_signals": buy_signals,
            "sell_signals": sell_signals,
            "hold_signals": hold_signals,
            "ending_equity": ending_equity,
            "net_pnl": net_pnl,
            "return_pct": return_pct,
            "max_drawdown_pct": round(max_drawdown_pct, 4),
            "total_realized_pnl": final_portfolio["total_realized_pnl"],
            "total_unrealized_pnl": final_portfolio["total_unrealized_pnl"],
            "order_count": final_portfolio["order_count"],
        }
