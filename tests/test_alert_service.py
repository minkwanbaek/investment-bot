from investment_bot.services.alert_service import AlertService


def test_alert_service_detects_unrealized_pnl_breach():
    service = AlertService(unrealized_pnl_threshold=-10, drawdown_pct_threshold=10)
    alerts = service.evaluate_portfolio(
        {
            "starting_cash": 1000,
            "total_equity": 980,
            "total_unrealized_pnl": -20,
        }
    )
    assert any(alert["kind"] == "unrealized_pnl_breach" for alert in alerts)


def test_alert_service_detects_drawdown_breach():
    service = AlertService(unrealized_pnl_threshold=-100, drawdown_pct_threshold=1)
    alerts = service.evaluate_portfolio(
        {
            "starting_cash": 1000,
            "total_equity": 980,
            "total_unrealized_pnl": 0,
        }
    )
    assert any(alert["kind"] == "drawdown_breach" for alert in alerts)
