from investment_bot.services.run_history_service import RunHistoryService
from investment_bot.services.run_history_store import RunHistoryStore
from investment_bot.services.shadow_service import ShadowService


class FakePaperBroker:
    def __init__(self):
        self.synced = None

    def sync_exchange_position(self, symbol: str, quantity: float, average_price: float, cash_balance: float | None = None):
        self.synced = {
            "symbol": symbol,
            "quantity": quantity,
            "average_price": average_price,
            "cash_balance": cash_balance,
        }


class FakeSemiLiveService:
    def __init__(self):
        self.trading_cycle_service = type("T", (), {"paper_broker": FakePaperBroker()})()
        self.calls = []

    def run_once(self, strategy_name: str, symbol: str, timeframe: str, limit: int = 5, record_history: bool = True):
        self.calls.append({"record_history": record_history})
        return {
            "adapter": "live",
            "strategy": strategy_name,
            "symbol": symbol,
            "timeframe": timeframe,
            "limit": limit,
            "signal": {"strategy_name": strategy_name, "symbol": symbol, "action": "hold", "confidence": 0.0, "reason": "test"},
            "review": {"approved": False, "action": "hold", "reason": "test", "target_notional": 0.0, "size_scale": 0.0},
            "portfolio": {"total_equity": 99999},
            "broker_result": None,
        }


class FakeUpbitClient:
    def get_balances(self):
        return [{"currency": "KRW", "balance": "1000", "locked": "0"}]


class FakeAccountService:
    def summarize_upbit_balances(self):
        return {
            "exchange": "upbit",
            "krw_cash": 12345.0,
            "asset_count": 1,
            "assets": [{"currency": "BTC", "balance": 0.25, "avg_buy_price": 100000000.0}],
        }

    def get_asset_balance(self, symbol: str):
        return {
            "currency": "BTC",
            "balance": 0.25,
            "locked": 0.0,
            "total_balance": 0.25,
            "avg_buy_price": 100000000.0,
            "estimated_cost_basis": 25000000.0,
        }


def test_shadow_service_syncs_exchange_balance_into_paper_broker(tmp_path):
    semi_live = FakeSemiLiveService()
    run_history = RunHistoryService(store=RunHistoryStore(str(tmp_path / 'run_history.json')))
    service = ShadowService(
        semi_live_service=semi_live,
        run_history_service=run_history,
        upbit_client=FakeUpbitClient(),
        account_service=FakeAccountService(),
    )

    result = service.run_once(strategy_name='trend_following', symbol='BTC/KRW', timeframe='1h', limit=8)

    assert result['mode'] == 'shadow'
    synced = semi_live.trading_cycle_service.paper_broker.synced
    assert synced['symbol'] == 'BTC/KRW'
    assert synced['quantity'] == 0.25
    assert synced['average_price'] == 100000000.0
    assert synced['cash_balance'] == 12345.0
    assert semi_live.calls[-1]['record_history'] is False
    assert 'exchange_balances' not in result
    assert 'portfolio' not in result['decision']

    recorded = run_history.list_recent(limit=10)
    assert len(recorded) == 1
    payload = recorded[0]['payload']
    assert payload['decision']['signal']['action'] == 'hold'
    assert 'portfolio' not in payload['decision']
