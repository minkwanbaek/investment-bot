import json

from investment_bot.services.ledger_store import LedgerStore
from investment_bot.services.paper_broker import PaperBroker


def test_ledger_store_persists_broker_state(tmp_path):
    ledger_path = tmp_path / "paper_ledger.json"
    store = LedgerStore(str(ledger_path))

    broker = PaperBroker(starting_cash=1000, ledger_store=store, trading_fee_pct=0.0, slippage_pct=0.0, min_order_notional=0.0)
    broker.submit(
        {
            "strategy_name": "trend_following",
            "symbol": "BTC/KRW",
            "action": "buy",
            "confidence": 1.0,
            "size_scale": 1.0,
            "reason": "buy",
        },
        execution_price=100,
    )
    broker.mark_price("BTC/KRW", 120)

    assert ledger_path.exists()
    payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert payload["cash_balance"] == 900.0
    assert payload["portfolio"]["total_unrealized_pnl"] == 20.0

    restored = PaperBroker(starting_cash=1000, ledger_store=store, trading_fee_pct=0.0, slippage_pct=0.0, min_order_notional=0.0)
    snapshot = restored.portfolio_snapshot()
    assert snapshot["cash_balance"] == 900.0
    assert snapshot["positions"]["BTC/KRW"]["market_price"] == 120.0
    assert snapshot["order_count"] == 1
