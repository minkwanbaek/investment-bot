from investment_bot.core.settings import Settings
from investment_bot.services.auto_trade_service import AutoTradeService
from investment_bot.services.run_history_service import RunHistoryService
from investment_bot.services.run_history_store import RunHistoryStore


class FakeShadowService:
    def run_once(self, strategy_name: str, symbol: str, timeframe: str, limit: int = 5):
        return {
            "decision": {
                "review": {
                    "action": "buy",
                    "latest_price": 1000.0,
                }
            }
        }


class FakeLiveExecutionService:
    def preview_order(self, symbol: str, side: str, price: float, volume: float):
        return {"allowed": True, "symbol": symbol, "side": side, "price": price, "volume": volume}

    def submit_order(self, symbol: str, side: str, price: float, volume: float):
        return {"status": "submitted", "symbol": symbol, "side": side, "price": price, "volume": volume}


class FakeAccountService:
    def __init__(self, krw_cash: float):
        self.krw_cash = krw_cash

    def summarize_upbit_balances(self):
        return {"exchange": "upbit", "krw_cash": self.krw_cash, "asset_count": 0, "assets": []}


def test_auto_trade_service_skips_when_krw_balance_is_below_threshold(tmp_path):
    history = RunHistoryService(store=RunHistoryStore(str(tmp_path / 'run_history.json')))
    service = AutoTradeService(
        settings=Settings(auto_trade_min_krw_balance=15000, auto_trade_target_allocation_pct=20, auto_trade_meaningful_order_notional=10000),
        shadow_service=FakeShadowService(),
        live_execution_service=FakeLiveExecutionService(),
        account_service=FakeAccountService(krw_cash=5000),
        run_history_service=history,
    )

    result = service.run_once()

    assert result['status'] == 'skipped'
    assert result['reason'] == 'insufficient_krw_balance'


def test_auto_trade_service_submits_when_profile_conditions_are_met(tmp_path):
    history = RunHistoryService(store=RunHistoryStore(str(tmp_path / 'run_history.json')))
    service = AutoTradeService(
        settings=Settings(auto_trade_min_krw_balance=15000, auto_trade_target_allocation_pct=20, auto_trade_meaningful_order_notional=10000, min_order_notional=5000),
        shadow_service=FakeShadowService(),
        live_execution_service=FakeLiveExecutionService(),
        account_service=FakeAccountService(krw_cash=55000),
        run_history_service=history,
    )

    result = service.run_once()

    assert result['status'] == 'submitted'
    assert result['submit']['status'] == 'submitted'
    assert result['preview']['allowed'] is True
