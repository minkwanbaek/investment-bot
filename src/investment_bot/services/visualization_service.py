from dataclasses import dataclass

from investment_bot.services.run_history_service import RunHistoryService


@dataclass
class VisualizationService:
    run_history_service: RunHistoryService

    def summarize_profit_structure(self, limit: int = 50) -> dict:
        runs = self.run_history_service.list_recent(limit=limit)
        equity_curve = []
        pnl_waterfall = []
        stop_reason_counts: dict[str, int] = {}
        kind_counts: dict[str, int] = {}

        for run in runs:
            kind = run["kind"]
            kind_counts[kind] = kind_counts.get(kind, 0) + 1
            payload = run.get("payload", {})

            portfolio = payload.get("final_portfolio") or payload.get("portfolio")
            if portfolio and "total_equity" in portfolio:
                equity_curve.append(
                    {
                        "run_id": run["id"],
                        "kind": kind,
                        "created_at": run["created_at"],
                        "total_equity": portfolio["total_equity"],
                        "realized_pnl": portfolio.get("total_realized_pnl", 0.0),
                        "unrealized_pnl": portfolio.get("total_unrealized_pnl", 0.0),
                    }
                )
                pnl_waterfall.append(
                    {
                        "run_id": run["id"],
                        "kind": kind,
                        "label": f"{kind}#{run['id']}",
                        "realized_pnl": portfolio.get("total_realized_pnl", 0.0),
                        "unrealized_pnl": portfolio.get("total_unrealized_pnl", 0.0),
                    }
                )

            stop_reason = payload.get("fail_safe", {}).get("stop_reason")
            if stop_reason:
                stop_reason_counts[stop_reason] = stop_reason_counts.get(stop_reason, 0) + 1

        latest_equity = equity_curve[-1]["total_equity"] if equity_curve else None
        return {
            "limit": limit,
            "run_count": len(runs),
            "latest_equity": latest_equity,
            "equity_curve": equity_curve,
            "pnl_waterfall": pnl_waterfall,
            "kind_counts": kind_counts,
            "stop_reason_counts": stop_reason_counts,
            "recommended_charts": [
                {"type": "line", "field": "equity_curve", "why": "Track total equity over time"},
                {"type": "waterfall", "field": "pnl_waterfall", "why": "Break down realized and unrealized contribution by run"},
                {"type": "bar", "field": "kind_counts", "why": "Show operational mix by run type"},
                {"type": "bar", "field": "stop_reason_counts", "why": "Show why fail-safe stops occurred"},
            ],
        }
