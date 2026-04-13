from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any


TRADE_LOG_METRIC_KEYS = (
    "total_trades",
    "win_rate",
    "avg_win",
    "avg_loss",
    "profit_factor",
    "expectancy",
    "max_drawdown",
    "total_net_pnl",
)


@dataclass
class MetricsService:
    def _time_bucket(self, entry_time: str | None) -> str:
        if not entry_time:
            return "unknown"
        dt = datetime.fromisoformat(str(entry_time).replace("Z", "+00:00"))
        return f"{dt.hour:02d}:00"

    def _holding_time_bucket(self, holding_seconds: Any) -> str:
        seconds = float(holding_seconds or 0.0)
        if seconds < 60:
            return "lt_1m"
        if seconds < 300:
            return "1m_to_5m"
        if seconds < 3600:
            return "5m_to_1h"
        return "gte_1h"

    def build_loss_pattern_report(self, trade_logs: list[dict], top_n: int = 10) -> list[dict]:
        losses = [log for log in trade_logs if float(log.get("net_pnl", 0.0) or 0.0) < 0]
        grouped: dict[tuple[str, str, str, str, str, str], list[dict]] = defaultdict(list)
        for log in losses:
            key = (
                log.get("entry_reason") or "unknown",
                log.get("symbol") or "unknown",
                log.get("market_regime") or "unknown",
                log.get("volatility_state") or "unknown",
                self._holding_time_bucket(log.get("holding_seconds")),
                self._time_bucket(log.get("entry_time")),
            )
            grouped[key].append(log)

        rows = []
        for key, items in grouped.items():
            summary = self.summarize_trade_logs(items)
            rows.append({
                "entry_reason": key[0],
                "symbol": key[1],
                "market_regime": key[2],
                "volatility_state": key[3],
                "holding_time_bucket": key[4],
                "time_bucket": key[5],
                **summary,
            })
        rows.sort(key=lambda row: row["total_net_pnl"])
        return rows[:top_n]

    def summarize_trade_logs_by_hour(self, trade_logs: list[dict]) -> dict:
        grouped: dict[str, list[dict]] = defaultdict(list)
        for log in trade_logs:
            grouped[self._time_bucket(log.get("entry_time"))].append(log)
        return {bucket: self.summarize_trade_logs(items) for bucket, items in grouped.items()}

    def summarize_trade_logs_by_symbol_rank(self, trade_logs: list[dict]) -> dict:
        by_symbol = self.summarize_trade_logs_by_dimension(trade_logs).get("by_symbol", {})
        ranked = sorted(by_symbol.items(), key=lambda item: item[1]["total_net_pnl"])
        return {
            "worst": [{"symbol": key, **value} for key, value in ranked],
            "best": [{"symbol": key, **value} for key, value in reversed(ranked)],
        }

    def summarize_trade_logs_by_market_state(self, trade_logs: list[dict]) -> dict:
        by_regime = self.summarize_trade_logs_by_dimension(trade_logs).get("by_market_regime", {})
        grouped: dict[str, list[dict]] = defaultdict(list)
        for log in trade_logs:
            state_key = f"{log.get('market_regime') or 'unknown'}|{log.get('volatility_state') or 'unknown'}|{log.get('higher_tf_bias') or 'unknown'}"
            grouped[state_key].append(log)
        combined = {bucket: self.summarize_trade_logs(items) for bucket, items in grouped.items()}
        return {
            "by_market_regime": by_regime,
            "by_combined_state": combined,
        }

    def summarize_trade_logs(self, trade_logs: list[dict]) -> dict:
        total_trades = len(trade_logs)
        net_pnls = [float(log.get("net_pnl", 0.0) or 0.0) for log in trade_logs]
        wins = [p for p in net_pnls if p > 0]
        losses = [p for p in net_pnls if p < 0]
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        avg_win = round(gross_profit / len(wins), 4) if wins else 0.0
        avg_loss = round(abs(sum(losses)) / len(losses), 4) if losses else 0.0
        win_rate = round((len(wins) / total_trades) * 100, 4) if total_trades else 0.0
        profit_factor = round(gross_profit / gross_loss, 4) if gross_loss else None
        expectancy = round(sum(net_pnls) / total_trades, 4) if total_trades else 0.0

        equity = 0.0
        peak = 0.0
        max_drawdown = 0.0
        for pnl in net_pnls:
            equity += pnl
            peak = max(peak, equity)
            drawdown = peak - equity
            max_drawdown = max(max_drawdown, drawdown)

        return {
            "total_trades": total_trades,
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
            "expectancy": expectancy,
            "max_drawdown": round(max_drawdown, 4),
            "total_net_pnl": round(sum(net_pnls), 4),
        }

    def summarize_trade_logs_by_dimension(self, trade_logs: list[dict]) -> dict:
        grouped: dict[str, dict[str, list[dict]]] = {
            "overall": {"all": list(trade_logs)},
            "by_day": defaultdict(list),
            "by_week": defaultdict(list),
            "by_symbol": defaultdict(list),
            "by_strategy_version": defaultdict(list),
            "by_market_regime": defaultdict(list),
        }

        for log in trade_logs:
            entry_time = log.get("entry_time")
            day_key = "unknown"
            week_key = "unknown"
            if entry_time:
                dt = datetime.fromisoformat(str(entry_time).replace("Z", "+00:00"))
                day_key = dt.date().isoformat()
                iso = dt.isocalendar()
                week_key = f"{iso.year}-W{iso.week:02d}"
            grouped["by_day"][day_key].append(log)
            grouped["by_week"][week_key].append(log)
            grouped["by_symbol"][log.get("symbol") or "unknown"].append(log)
            grouped["by_strategy_version"][log.get("strategy_version") or "unknown"].append(log)
            grouped["by_market_regime"][log.get("market_regime") or "unknown"].append(log)

        summary = {}
        for dimension, buckets in grouped.items():
            summary[dimension] = {bucket: self.summarize_trade_logs(items) for bucket, items in buckets.items()}
        return summary

    def summarize_backtest(self, starting_cash: float, runs: list[dict], final_portfolio: dict) -> dict:
        total_steps = len(runs)
        approved_orders = sum(1 for run in runs if run["review"]["approved"])
        buy_signals = sum(1 for run in runs if run["signal"]["action"] == "buy")
        sell_signals = sum(1 for run in runs if run["signal"]["action"] == "sell")
        hold_signals = sum(1 for run in runs if run["signal"]["action"] == "hold")

        equity_curve = [starting_cash] + [run["portfolio"]["total_equity"] for run in runs]
        ending_equity = final_portfolio["total_equity"]
        net_pnl = round(ending_equity - starting_cash, 4)
        return_pct = round((net_pnl / starting_cash) * 100, 4) if starting_cash else 0.0
        max_equity = starting_cash
        max_drawdown_pct = 0.0
        winning_steps = 0
        losing_steps = 0
        gross_profit = 0.0
        gross_loss = 0.0

        for prev_equity, equity in zip(equity_curve, equity_curve[1:]):
            pnl_change = round(equity - prev_equity, 4)
            if pnl_change > 0:
                winning_steps += 1
                gross_profit += pnl_change
            elif pnl_change < 0:
                losing_steps += 1
                gross_loss += abs(pnl_change)
            max_equity = max(max_equity, equity)
            drawdown_pct = ((max_equity - equity) / max_equity * 100) if max_equity else 0.0
            max_drawdown_pct = max(max_drawdown_pct, drawdown_pct)

        win_rate_pct = round((winning_steps / total_steps) * 100, 4) if total_steps else 0.0
        profit_factor = round(gross_profit / gross_loss, 4) if gross_loss else None

        return {
            "total_steps": total_steps,
            "approved_orders": approved_orders,
            "buy_signals": buy_signals,
            "sell_signals": sell_signals,
            "hold_signals": hold_signals,
            "winning_steps": winning_steps,
            "losing_steps": losing_steps,
            "win_rate_pct": win_rate_pct,
            "gross_profit": round(gross_profit, 4),
            "gross_loss": round(gross_loss, 4),
            "profit_factor": profit_factor,
            "equity_curve": equity_curve,
            "ending_equity": ending_equity,
            "net_pnl": net_pnl,
            "return_pct": return_pct,
            "max_drawdown_pct": round(max_drawdown_pct, 4),
            "total_realized_pnl": final_portfolio["total_realized_pnl"],
            "total_unrealized_pnl": final_portfolio["total_unrealized_pnl"],
            "order_count": final_portfolio["order_count"],
        }
