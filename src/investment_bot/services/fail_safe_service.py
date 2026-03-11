from dataclasses import dataclass

from investment_bot.services.alert_service import AlertService


@dataclass
class FailSafeService:
    alert_service: AlertService
    max_alerts_per_batch: int = 1
    max_loss_steps: int = 2

    def evaluate_batch(self, runs: list[dict]) -> dict:
        total_alerts = 0
        consecutive_loss_steps = 0
        stop_reason = None

        for run in runs:
            portfolio = run.get("portfolio", {})
            alerts = self.alert_service.evaluate_portfolio(portfolio)
            total_alerts += len(alerts)

            total_equity = portfolio.get("total_equity", portfolio.get("starting_cash", 0.0))
            starting_cash = portfolio.get("starting_cash", 0.0)
            if total_equity < starting_cash:
                consecutive_loss_steps += 1
            else:
                consecutive_loss_steps = 0

            if total_alerts >= self.max_alerts_per_batch:
                stop_reason = "max_alerts_reached"
                break
            if consecutive_loss_steps >= self.max_loss_steps:
                stop_reason = "max_consecutive_loss_steps_reached"
                break

        return {
            "stop": stop_reason is not None,
            "stop_reason": stop_reason,
            "total_alerts": total_alerts,
            "consecutive_loss_steps": consecutive_loss_steps,
        }
