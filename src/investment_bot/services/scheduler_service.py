from dataclasses import dataclass
import time

from investment_bot.services.fail_safe_service import FailSafeService
from investment_bot.services.run_history_service import RunHistoryService
from investment_bot.services.semi_live_service import SemiLiveService


@dataclass
class SchedulerService:
    semi_live_service: SemiLiveService
    run_history_service: RunHistoryService
    fail_safe_service: FailSafeService

    def run_semi_live_batch(
        self,
        strategy_name: str,
        symbol: str,
        timeframe: str,
        limit: int,
        iterations: int,
        interval_seconds: float = 0.0,
    ) -> dict:
        if iterations < 1:
            raise ValueError("iterations must be >= 1")
        if interval_seconds < 0:
            raise ValueError("interval_seconds must be >= 0")

        runs = []
        fail_safe = {"stop": False, "stop_reason": None, "total_alerts": 0, "consecutive_loss_steps": 0}
        for index in range(iterations):
            result = self.semi_live_service.run_once(
                strategy_name=strategy_name,
                symbol=symbol,
                timeframe=timeframe,
                limit=limit,
            )
            runs.append(result)
            fail_safe = self.fail_safe_service.evaluate_batch(runs)
            if fail_safe["stop"]:
                break
            if interval_seconds > 0 and index < iterations - 1:
                time.sleep(interval_seconds)

        summary = {
            "kind": "semi_live_batch",
            "strategy_name": strategy_name,
            "symbol": symbol,
            "timeframe": timeframe,
            "limit": limit,
            "iterations": iterations,
            "completed_iterations": len(runs),
            "interval_seconds": interval_seconds,
            "fail_safe": fail_safe,
            "final_portfolio": runs[-1]["portfolio"],
            "runs": runs,
        }
        self.run_history_service.record(kind="semi_live_batch", payload=summary)
        return summary
