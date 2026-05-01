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


def test_alert_service_detects_auto_trade_watchdog_warning():
    service = AlertService()
    alerts = service.evaluate_auto_trade_status(
        {
            "watchdog": {
                "health": "warning",
                "warnings": ["no_submission_since_start"],
                "minutes_since_last_submission": None,
                "minutes_since_last_nonempty_batch": 12.5,
            }
        }
    )
    assert len(alerts) == 1
    assert alerts[0]["kind"] == "auto_trade_watchdog"
    assert alerts[0]["severity"] == "warning"
    assert "no_submission_since_start" in alerts[0]["warnings"]


def test_alert_service_detects_auto_trade_watchdog_degraded():
    service = AlertService()
    alerts = service.evaluate_auto_trade_status(
        {
            "watchdog": {
                "health": "degraded",
                "warnings": ["zero_evaluated_symbols_streak"],
                "minutes_since_last_submission": 45.0,
                "minutes_since_last_nonempty_batch": 45.0,
            }
        }
    )
    assert len(alerts) == 1
    assert alerts[0]["severity"] == "critical"
    assert alerts[0]["health"] == "degraded"
