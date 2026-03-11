from investment_bot.services.alert_service import AlertService
from investment_bot.services.fail_safe_service import FailSafeService


def test_fail_safe_stops_on_alert_threshold():
    service = FailSafeService(
        alert_service=AlertService(unrealized_pnl_threshold=-1, drawdown_pct_threshold=10),
        max_alerts_per_batch=1,
        max_loss_steps=2,
    )
    result = service.evaluate_batch(
        [
            {
                "portfolio": {
                    "starting_cash": 1000,
                    "total_equity": 995,
                    "total_unrealized_pnl": -5,
                }
            }
        ]
    )
    assert result["stop"] is True
    assert result["stop_reason"] == "max_alerts_reached"


def test_fail_safe_stops_on_consecutive_loss_steps():
    service = FailSafeService(
        alert_service=AlertService(),
        max_alerts_per_batch=3,
        max_loss_steps=2,
    )
    result = service.evaluate_batch(
        [
            {"portfolio": {"starting_cash": 1000, "total_equity": 999, "total_unrealized_pnl": 0}},
            {"portfolio": {"starting_cash": 1000, "total_equity": 998, "total_unrealized_pnl": 0}},
        ]
    )
    assert result["stop"] is True
    assert result["stop_reason"] == "max_consecutive_loss_steps_reached"
