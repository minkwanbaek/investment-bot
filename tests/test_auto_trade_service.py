from investment_bot.core.settings import Settings
from investment_bot.services.auto_trade_service import AutoTradeService
from investment_bot.services.run_history_service import RunHistoryService
from investment_bot.services.run_history_store import RunHistoryStore


class FakeShadowService:
    def __init__(self, by_symbol=None):
        self.by_symbol = by_symbol or {
            "BTC/KRW": {"action": "buy", "latest_price": 1000.0, "confidence": 0.5, "target_notional": 6000.0, "market_regime": {"regime": "uptrend"}},
        }

    def run_once(self, strategy_name: str, symbol: str, timeframe: str, limit: int = 5):
        cfg = self.by_symbol[symbol]
        return {
            "decision": {
                "review": {
                    "action": cfg["action"],
                    "latest_price": cfg["latest_price"],
                    "confidence": cfg["confidence"],
                    "target_notional": cfg["target_notional"],
                },
                "market_regime": cfg.get("market_regime", {"regime": "unknown"}),
            }
        }


class FakeLiveExecutionService:
    def preview_order(self, symbol: str, side: str, price: float, volume: float):
        return {"allowed": True, "symbol": symbol, "side": side, "price": price, "volume": volume}

    def submit_order(self, symbol: str, side: str, price: float, volume: float):
        return {"status": "submitted", "symbol": symbol, "side": side, "price": price, "volume": volume}


class FakeAccountService:
    def __init__(self, krw_cash: float, asset_balances=None, avg_buy_prices=None):
        self.krw_cash = krw_cash
        self.asset_balances = asset_balances or {}
        self.avg_buy_prices = avg_buy_prices or {}

    def summarize_upbit_balances(self):
        assets = []
        for sym, bal in self.asset_balances.items():
            asset = sym.split('/')[0]
            avg = self.avg_buy_prices.get(sym, 1000.0)
            assets.append({"currency": asset, "balance": bal, "estimated_cost_basis": bal * avg})
        return {"exchange": "upbit", "krw_cash": self.krw_cash, "asset_count": len(assets), "assets": assets}

    def get_asset_balance(self, symbol: str):
        bal = self.asset_balances.get(symbol, 0.0)
        avg = self.avg_buy_prices.get(symbol, 1000.0)
        return {"currency": symbol.split('/')[0], "balance": bal, "locked": 0.0, "total_balance": bal, "avg_buy_price": avg, "estimated_cost_basis": bal * avg}


def test_auto_trade_service_skips_when_krw_balance_is_below_threshold(tmp_path):
    history = RunHistoryService(store=RunHistoryStore(str(tmp_path / 'run_history.json')))
    service = AutoTradeService(
        settings=Settings(symbols=["BTC/KRW"], auto_trade_min_krw_balance=15000, auto_trade_target_allocation_pct=20, auto_trade_meaningful_order_notional=10000),
        shadow_service=FakeShadowService({"BTC/KRW": {"action": "buy", "latest_price": 1000.0, "confidence": 0.5, "target_notional": 6000.0}}),
        live_execution_service=FakeLiveExecutionService(),
        account_service=FakeAccountService(krw_cash=5000),
        run_history_service=history,
    )
    result = service.run_once()
    assert result['status'] == 'skipped'
    assert result['reason'] == 'insufficient_krw_balance'


def test_auto_trade_service_submits_buy_when_profile_conditions_are_met(tmp_path):
    history = RunHistoryService(store=RunHistoryStore(str(tmp_path / 'run_history.json')))
    service = AutoTradeService(
        settings=Settings(symbols=["BTC/KRW"], auto_trade_min_krw_balance=15000, auto_trade_target_allocation_pct=20, auto_trade_meaningful_order_notional=5000, min_order_notional=5000),
        shadow_service=FakeShadowService({"BTC/KRW": {"action": "buy", "latest_price": 1000.0, "confidence": 0.5, "target_notional": 6000.0}}),
        live_execution_service=FakeLiveExecutionService(),
        account_service=FakeAccountService(krw_cash=55000),
        run_history_service=history,
    )
    result = service.run_once()
    assert result['status'] == 'submitted'
    assert result['side'] == 'buy'
    assert result['submit']['volume'] == 6.0


def test_auto_trade_service_caps_buy_by_review_target_notional(tmp_path):
    history = RunHistoryService(store=RunHistoryStore(str(tmp_path / 'run_history.json')))
    service = AutoTradeService(
        settings=Settings(symbols=["BTC/KRW"], auto_trade_min_krw_balance=15000, auto_trade_target_allocation_pct=20, auto_trade_meaningful_order_notional=5000, min_order_notional=5000),
        shadow_service=FakeShadowService({"BTC/KRW": {"action": "buy", "latest_price": 1000.0, "confidence": 0.5, "target_notional": 5200.0}}),
        live_execution_service=FakeLiveExecutionService(),
        account_service=FakeAccountService(krw_cash=100000),
        run_history_service=history,
    )
    result = service.run_once()
    assert result['status'] == 'submitted'
    assert result['submit']['volume'] == 5.2


def test_auto_trade_service_enforces_total_exposure_limit_before_buy(tmp_path):
    history = RunHistoryService(store=RunHistoryStore(str(tmp_path / 'run_history.json')))
    service = AutoTradeService(
        settings=Settings(symbols=["BTC/KRW"], auto_trade_min_krw_balance=15000, auto_trade_target_allocation_pct=20, auto_trade_meaningful_order_notional=5000, min_order_notional=5000, auto_trade_max_total_exposure_pct=60.0),
        shadow_service=FakeShadowService({"BTC/KRW": {"action": "buy", "latest_price": 1000.0, "confidence": 0.7, "target_notional": 10000.0}}),
        live_execution_service=FakeLiveExecutionService(),
        account_service=FakeAccountService(krw_cash=20000, asset_balances={"ETH/KRW": 0.5}, avg_buy_prices={"ETH/KRW": 100000.0}),
        run_history_service=history,
    )
    result = service.run_once()
    assert result['status'] == 'skipped'
    assert result['reason'] == 'below_meaningful_order_notional_or_total_exposure_limit'


def test_auto_trade_service_prefers_sell_over_buy_across_symbols(tmp_path):
    history = RunHistoryService(store=RunHistoryStore(str(tmp_path / 'run_history.json')))
    shadow = FakeShadowService({
        "BTC/KRW": {"action": "buy", "latest_price": 1000.0, "confidence": 0.9, "target_notional": 6000.0},
        "ETH/KRW": {"action": "sell", "latest_price": 2000.0, "confidence": 0.4, "target_notional": 0.0},
    })
    service = AutoTradeService(
        settings=Settings(symbols=["BTC/KRW", "ETH/KRW"], auto_trade_min_managed_position_notional=10000.0),
        shadow_service=shadow,
        live_execution_service=FakeLiveExecutionService(),
        account_service=FakeAccountService(krw_cash=50000, asset_balances={"ETH/KRW": 10.0}, avg_buy_prices={"ETH/KRW": 2000.0}),
        run_history_service=history,
    )
    result = service.run_once()
    assert result['status'] == 'submitted'
    assert result['symbol'] == 'ETH/KRW'
    assert result['side'] == 'sell'


def test_auto_trade_service_submits_sell_using_exchange_balance(tmp_path):
    history = RunHistoryService(store=RunHistoryStore(str(tmp_path / 'run_history.json')))
    service = AutoTradeService(
        settings=Settings(symbols=["BTC/KRW"], auto_trade_min_krw_balance=15000, auto_trade_target_allocation_pct=20, auto_trade_meaningful_order_notional=10000, min_order_notional=5000, auto_trade_min_managed_position_notional=100.0),
        shadow_service=FakeShadowService({"BTC/KRW": {"action": "sell", "latest_price": 1000.0, "confidence": 0.8, "target_notional": 0.0}}),
        live_execution_service=FakeLiveExecutionService(),
        account_service=FakeAccountService(krw_cash=0, asset_balances={"BTC/KRW": 0.25}, avg_buy_prices={"BTC/KRW": 900.0}),
        run_history_service=history,
    )
    result = service.run_once()
    assert result['status'] == 'submitted'
    assert result['side'] == 'sell'
    assert result['submit']['volume'] == 0.2


def test_auto_trade_service_skips_dust_positions_below_min_managed_notional(tmp_path):
    history = RunHistoryService(store=RunHistoryStore(str(tmp_path / 'run_history.json')))
    service = AutoTradeService(
        settings=Settings(symbols=["SOL/KRW"], auto_trade_min_managed_position_notional=10000.0),
        shadow_service=FakeShadowService({"SOL/KRW": {"action": "sell", "latest_price": 132800.0, "confidence": 0.4, "target_notional": 0.0}}),
        live_execution_service=FakeLiveExecutionService(),
        account_service=FakeAccountService(krw_cash=0, asset_balances={"SOL/KRW": 0.00007428}, avg_buy_prices={"SOL/KRW": 257501.2175}),
        run_history_service=history,
    )
    result = service.run_once()
    assert result['status'] == 'skipped'
    assert result['reason'] == 'below_min_managed_position_notional'


def test_auto_trade_service_stop_loss_uses_price_pct_not_quantity(tmp_path):
    history = RunHistoryService(store=RunHistoryStore(str(tmp_path / 'run_history.json')))
    service = AutoTradeService(
        settings=Settings(symbols=["BTC/KRW"], auto_trade_stop_loss_pct=1.5, auto_trade_partial_take_profit_pct=2.0, auto_trade_trailing_stop_pct=1.0, auto_trade_partial_sell_ratio=0.5, auto_trade_min_managed_position_notional=10.0),
        shadow_service=FakeShadowService({"BTC/KRW": {"action": "hold", "latest_price": 98000.0, "confidence": 0.0, "target_notional": 0.0}}),
        live_execution_service=FakeLiveExecutionService(),
        account_service=FakeAccountService(krw_cash=0.0, asset_balances={"BTC/KRW": 0.00060394}, avg_buy_prices={"BTC/KRW": 100000.0}),
        run_history_service=history,
    )
    result = service.run_once()
    assert result['status'] == 'submitted'
    assert result['override']['override_reason'] == 'stop_loss'
    assert result['submit']['volume'] == 0.00060394


def test_auto_trade_service_take_profit_trailing_stop_with_small_btc_quantity(tmp_path):
    history = RunHistoryService(store=RunHistoryStore(str(tmp_path / 'run_history.json')))
    service = AutoTradeService(
        settings=Settings(symbols=["BTC/KRW"], auto_trade_stop_loss_pct=1.5, auto_trade_partial_take_profit_pct=2.0, auto_trade_trailing_stop_pct=1.0, auto_trade_partial_sell_ratio=0.5, auto_trade_min_managed_position_notional=10.0),
        shadow_service=FakeShadowService({"BTC/KRW": {"action": "hold", "latest_price": 102000.0, "confidence": 0.0, "target_notional": 0.0}}),
        live_execution_service=FakeLiveExecutionService(),
        account_service=FakeAccountService(krw_cash=0.0, asset_balances={"BTC/KRW": 0.00060394}, avg_buy_prices={"BTC/KRW": 100000.0}),
        run_history_service=history,
    )
    service._peak_price_by_symbol['BTC/KRW'] = 103500.0
    result = service.run_once()
    assert result['status'] == 'submitted'
    assert result['override']['override_reason'] == 'take_profit_trailing_stop'
    assert result['submit']['volume'] == 0.00030197
