from dataclasses import dataclass

from investment_bot.services.paper_broker import PaperBroker
from investment_bot.services.run_history_service import RunHistoryService


@dataclass
class DriftReportService:
    run_history_service: RunHistoryService
    paper_broker: PaperBroker

    def summarize(self, limit: int = 50) -> dict:
        runs = self.run_history_service.list_recent(limit=limit)
        latest_shadow = next((run for run in reversed(runs) if run.get("kind") == "shadow_cycle"), None)
        paper = self.paper_broker.portfolio_snapshot()

        if not latest_shadow:
            return {
                "status": "no_shadow_data",
                "paper_portfolio": paper,
                "shadow_reference": None,
                "position_drifts": [],
                "cash_drift": None,
                "recommendations": ["Run /cycle/shadow first to compare real exchange state against paper state"],
            }

        payload = latest_shadow.get("payload", {})
        account_summary = payload.get("exchange_account_summary") or {
            "krw_cash": 0.0,
            "assets": [],
            "asset_count": 0,
        }
        shadow_positions = self._shadow_positions(account_summary)
        paper_positions = self._paper_positions(paper)
        position_drifts = self._build_position_drifts(paper_positions, shadow_positions)
        cash_drift = round(paper.get("cash_balance", 0.0) - account_summary.get("krw_cash", 0.0), 4)

        return {
            "status": "ok",
            "paper_portfolio": paper,
            "shadow_reference": {
                "run_id": latest_shadow.get("id"),
                "created_at": latest_shadow.get("created_at"),
                "exchange_account_summary": account_summary,
            },
            "position_drifts": position_drifts,
            "cash_drift": {
                "paper_cash": round(paper.get("cash_balance", 0.0), 4),
                "shadow_cash": round(account_summary.get("krw_cash", 0.0), 4),
                "difference": cash_drift,
            },
            "recommendations": self._recommend(position_drifts, cash_drift),
        }

    def _paper_positions(self, paper: dict) -> dict[str, dict]:
        results: dict[str, dict] = {}
        for symbol, position in paper.get("positions", {}).items():
            base_asset = symbol.split("/")[0]
            results[base_asset] = {
                "symbol": symbol,
                "quantity": round(position.get("quantity", 0.0), 8),
                "average_price": round(position.get("average_price", 0.0), 4),
                "cost_basis": round(position.get("cost_basis", 0.0), 4),
            }
        return results

    def _shadow_positions(self, account_summary: dict) -> dict[str, dict]:
        results: dict[str, dict] = {}
        for asset in account_summary.get("assets", []):
            currency = asset.get("currency")
            results[currency] = {
                "quantity": round(float(asset.get("balance", 0.0) or 0.0), 8),
                "average_price": round(float(asset.get("avg_buy_price", 0.0) or 0.0), 4),
                "cost_basis": round(float(asset.get("estimated_cost_basis", 0.0) or 0.0), 4),
            }
        return results

    def _build_position_drifts(self, paper_positions: dict[str, dict], shadow_positions: dict[str, dict]) -> list[dict]:
        assets = sorted(set(paper_positions) | set(shadow_positions))
        drifts = []
        for asset in assets:
            paper = paper_positions.get(asset, {"quantity": 0.0, "average_price": 0.0, "cost_basis": 0.0, "symbol": f"{asset}/KRW"})
            shadow = shadow_positions.get(asset, {"quantity": 0.0, "average_price": 0.0, "cost_basis": 0.0})
            drifts.append(
                {
                    "asset": asset,
                    "paper_symbol": paper.get("symbol", f"{asset}/KRW"),
                    "paper_quantity": paper["quantity"],
                    "shadow_quantity": shadow["quantity"],
                    "quantity_difference": round(paper["quantity"] - shadow["quantity"], 8),
                    "paper_average_price": paper["average_price"],
                    "shadow_average_price": shadow["average_price"],
                    "average_price_difference": round(paper["average_price"] - shadow["average_price"], 4),
                    "paper_cost_basis": paper["cost_basis"],
                    "shadow_cost_basis": shadow["cost_basis"],
                    "cost_basis_difference": round(paper["cost_basis"] - shadow["cost_basis"], 4),
                }
            )
        return drifts

    def _recommend(self, position_drifts: list[dict], cash_drift: float) -> list[str]:
        recommendations: list[str] = []
        meaningful_position_drift = any(
            abs(item["quantity_difference"]) > 0.00000001 or abs(item["cost_basis_difference"]) > 1
            for item in position_drifts
        )
        if meaningful_position_drift:
            recommendations.append("Review whether paper positions still reflect the latest real-account posture before trusting shadow comparisons")
        if abs(cash_drift) > 1000:
            recommendations.append("KRW cash drift is material; rebalance paper starting state or annotate why the real account differs")
        if not recommendations:
            recommendations.append("Paper and shadow states are close enough for continued shadow-mode monitoring")
        return recommendations
