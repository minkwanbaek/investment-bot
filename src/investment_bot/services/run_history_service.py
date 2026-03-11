from collections import Counter
from dataclasses import dataclass

from investment_bot.services.run_history_store import RunHistoryStore


@dataclass
class RunHistoryService:
    store: RunHistoryStore

    def record(self, kind: str, payload: dict) -> dict:
        return self.store.append(kind=kind, payload=payload)

    def list_recent(self, limit: int = 20) -> list[dict]:
        return self.store.list_recent(limit=limit)

    def summarize_recent(self, limit: int = 20) -> dict:
        runs = self.list_recent(limit=limit)
        kind_counts = Counter(run["kind"] for run in runs)
        stop_reasons = Counter(
            run.get("payload", {}).get("fail_safe", {}).get("stop_reason")
            for run in runs
            if run.get("payload", {}).get("fail_safe", {}).get("stop_reason")
        )
        latest_portfolio = None
        for run in reversed(runs):
            payload = run.get("payload", {})
            if "final_portfolio" in payload:
                latest_portfolio = payload["final_portfolio"]
                break
            if "portfolio" in payload:
                latest_portfolio = payload["portfolio"]
                break

        return {
            "total_runs": len(runs),
            "kind_counts": dict(kind_counts),
            "stop_reasons": dict(stop_reasons),
            "latest_portfolio": latest_portfolio,
        }

    def reset(self) -> dict:
        return self.store.reset()
