from dataclasses import dataclass


@dataclass
class AlertService:
    unrealized_pnl_threshold: float = 0.0
    drawdown_pct_threshold: float = 0.0

    def evaluate_portfolio(self, portfolio: dict) -> list[dict]:
        alerts: list[dict] = []
        if self.unrealized_pnl_threshold and portfolio["total_unrealized_pnl"] <= self.unrealized_pnl_threshold:
            alerts.append(
                {
                    "kind": "unrealized_pnl_breach",
                    "severity": "warning",
                    "message": f"Unrealized PnL breached threshold: {portfolio['total_unrealized_pnl']}",
                }
            )

        starting_cash = portfolio.get("starting_cash", 0.0)
        total_equity = portfolio.get("total_equity", 0.0)
        if self.drawdown_pct_threshold and starting_cash:
            drawdown_pct = ((starting_cash - total_equity) / starting_cash) * 100
            if drawdown_pct >= self.drawdown_pct_threshold:
                alerts.append(
                    {
                        "kind": "drawdown_breach",
                        "severity": "warning",
                        "message": f"Drawdown breached threshold: {drawdown_pct:.4f}%",
                    }
                )
        return alerts

    def evaluate_auto_trade_status(self, status: dict) -> list[dict]:
        watchdog = status.get("watchdog", {}) or {}
        warnings = list(watchdog.get("warnings", []) or [])
        if not warnings:
            return []

        health = watchdog.get("health", "warning")
        severity = "critical" if health == "degraded" else "warning"
        minutes_since_last_submission = watchdog.get("minutes_since_last_submission")
        minutes_since_last_nonempty_batch = watchdog.get("minutes_since_last_nonempty_batch")
        return [
            {
                "kind": "auto_trade_watchdog",
                "severity": severity,
                "message": (
                    f"auto-trade watchdog {health}: warnings={','.join(warnings)}; "
                    f"minutes_since_last_submission={minutes_since_last_submission}; "
                    f"minutes_since_last_nonempty_batch={minutes_since_last_nonempty_batch}"
                ),
                "warnings": warnings,
                "health": health,
            }
        ]
