from investment_bot.models.signal import TradeSignal
from investment_bot.risk.controller import RiskController


def test_risk_controller_holds_are_not_approved():
    rc = RiskController()
    reviewed = rc.review(TradeSignal(strategy_name="x", symbol="BTC/KRW", action="hold", confidence=0.1, reason="test"))
    assert reviewed["approved"] is False
    assert reviewed["size_scale"] == 0.0
