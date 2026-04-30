import json
import logging

import pytest

from investment_bot.core.settings import Settings
from investment_bot.services.auto_trade_service import AutoTradeService
from investment_bot.models.trade_log import TradeLogSchema
from investment_bot.services.ledger_store import LedgerStore
from investment_bot.services.paper_broker import PaperBroker
from investment_bot.services.run_history_service import RunHistoryService
from investment_bot.services.run_history_store import RunHistoryStore
from investment_bot.services.strategy_selection_service import StrategySelectionService


class FakeShadowService:
    def __init__(self, by_symbol_strategy=None):
        self.by_symbol_strategy = by_symbol_strategy or {
            ("BTC/KRW", "trend_following"): {"action": "buy", "latest_price": 1000.0, "confidence": 0.5, "target_notional": 6000.0, "market_regime": {"regime": "uptrend"}},
            ("BTC/KRW", "mean_reversion"): {"action": "hold", "latest_price": 1000.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "uptrend"}},
            ("BTC/KRW", "dca"): {"action": "hold", "latest_price": 1000.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "uptrend"}},
        }

    def invalidate_cache(self) -> None:
        pass

    def run_once(self, strategy_name: str, symbol: str, timeframe: str, limit: int = 5):
        cfg = self.by_symbol_strategy[(symbol, strategy_name)]
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


def test_paper_broker_appends_trade_log_entry_on_buy(tmp_path):
    ledger_path = tmp_path / 'ledger.json'
    broker = PaperBroker(starting_cash=100000.0, ledger_store=LedgerStore(str(ledger_path)), min_order_notional=5000.0)

    result = broker.submit(
        reviewed_signal={
            'strategy_name': 'trend_following',
            'symbol': 'BTC/KRW',
            'action': 'buy',
            'confidence': 0.8,
            'size_scale': 1.0,
            'reason': 'entry signal',
            'strategy_version': 'v1.0-base',
        },
        execution_price=10000.0,
    )

    assert result['status'] == 'recorded'
    payload = json.loads(ledger_path.read_text(encoding='utf-8'))
    trade_logs = payload.get('trade_logs', [])
    assert len(trade_logs) == 1
    entry = trade_logs[0]
    assert entry['symbol'] == 'BTC/KRW'
    assert entry['side'] == 'buy'
    assert entry['entry_price'] == 10005.0
    assert entry['quantity'] == 1.0
    assert entry['entry_reason'] == 'entry signal'
    assert entry['trade_id']
    assert entry['strategy_version'] == 'v1.0-base'
    assert entry['market_regime'] is None
    assert entry['volatility_state'] is None
    assert entry['higher_tf_bias'] is None


def test_ledger_store_trade_log_validation_rejects_missing_required_entry_field(tmp_path):
    ledger_store = LedgerStore(str(tmp_path / 'ledger.json'))

    try:
        ledger_store.append_trade_log_entry(
            TradeLogSchema(
                trade_id='test-1',
                strategy_version=None,
                symbol='BTC/KRW',
                side='buy',
                entry_time=None,
                entry_price=10000.0,
                quantity=1.0,
            )
        )
        assert False, 'expected validation failure'
    except Exception as exc:
        assert 'entry_time' in str(exc)


def test_paper_broker_updates_latest_open_trade_log_on_sell(tmp_path):
    ledger_path = tmp_path / 'ledger.json'
    broker = PaperBroker(starting_cash=100000.0, ledger_store=LedgerStore(str(ledger_path)), min_order_notional=5000.0)

    broker.submit(
        reviewed_signal={
            'strategy_name': 'trend_following',
            'symbol': 'BTC/KRW',
            'action': 'buy',
            'confidence': 0.8,
            'size_scale': 1.0,
            'reason': 'entry signal',
            'strategy_version': 'v1.0-base',
        },
        execution_price=10000.0,
    )
    sell_result = broker.submit(
        reviewed_signal={
            'strategy_name': 'trend_following',
            'symbol': 'BTC/KRW',
            'action': 'sell',
            'confidence': 0.8,
            'size_scale': 1.0,
            'reason': 'exit signal',
            'strategy_version': 'v1.0-base',
        },
        execution_price=10200.0,
    )

    assert sell_result['status'] == 'recorded'
    payload = json.loads(ledger_path.read_text(encoding='utf-8'))
    trade_logs = payload.get('trade_logs', [])
    assert len(trade_logs) == 1
    entry = trade_logs[0]
    assert entry['exit_price'] == 10194.9
    assert entry['exit_reason'] == 'exit signal'
    assert entry['exit_time'] is not None
    assert entry['gross_pnl'] == 184.8975
    assert entry['net_pnl'] == 179.8


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


class FakeDynamicSymbolSelector:
    def select(self, symbols: list[str], timeframe: str, top_n: int = 10) -> list[str]:
        return symbols[:top_n]


class FixedDynamicSymbolSelector:
    def __init__(self, selected: list[str]):
        self.selected = selected

    def select(self, symbols: list[str], timeframe: str, top_n: int = 10) -> list[str]:
        return list(self.selected)


def make_service(tmp_path, settings: Settings, shadow: FakeShadowService, account: FakeAccountService):
    return AutoTradeService(
        settings=settings,
        shadow_service=shadow,
        live_execution_service=FakeLiveExecutionService(),
        account_service=account,
        run_history_service=RunHistoryService(store=RunHistoryStore(str(tmp_path / 'run_history.json'))),
        strategy_selection_service=StrategySelectionService(),
    )


def test_paper_broker_appends_market_context_fields_on_buy(tmp_path):
    ledger_path = tmp_path / 'ledger.json'
    broker = PaperBroker(starting_cash=100000.0, ledger_store=LedgerStore(str(ledger_path)), min_order_notional=5000.0)

    result = broker.submit(
        reviewed_signal={
            'strategy_name': 'trend_following',
            'symbol': 'BTC/KRW',
            'action': 'buy',
            'confidence': 0.8,
            'size_scale': 1.0,
            'reason': 'entry signal',
            'strategy_version': 'v1.0-base',
            'market_regime': 'trend_up',
            'volatility_state': 'normal',
            'higher_tf_bias': 'bullish',
        },
        execution_price=10000.0,
    )

    assert result['status'] == 'recorded'
    payload = json.loads(ledger_path.read_text(encoding='utf-8'))
    entry = payload['trade_logs'][0]
    assert entry['market_regime'] == 'trend_up'
    assert entry['volatility_state'] == 'normal'
    assert entry['higher_tf_bias'] == 'bullish'


def test_trading_cycle_classifies_market_context_fields():
    from investment_bot.models.market import Candle
    from investment_bot.services.market_regime_classifier import MarketRegimeClassifier

    candles = []
    base = 10000.0
    for i in range(30):
        open_price = base + (i * 10)
        close_price = open_price + 30
        candles.append(
            Candle(
                symbol='BTC/KRW',
                timeframe='1h',
                open=open_price,
                high=close_price + 20,
                low=open_price - 20,
                close=close_price,
                volume=100 + i,
                timestamp=f'2026-01-01T{i:02d}:00:00Z',
            )
        )

    market = MarketRegimeClassifier().classify(candles)

    assert market['regime'] in {'trend_up', 'trend_down', 'sideways', 'uncertain'}
    assert market['volatility_state'] in {'low', 'normal', 'high'}
    assert market['higher_tf_bias'] in {'bullish', 'bearish', 'neutral'}


def test_market_regime_classifier_returns_expected_shape():
    from investment_bot.models.market import Candle
    from investment_bot.services.market_regime_classifier import MarketRegimeClassifier

    candles = []
    base = 10000.0
    for i in range(30):
        open_price = base + (i * 10)
        close_price = open_price + 30
        candles.append(
            Candle(
                symbol='BTC/KRW',
                timeframe='1h',
                open=open_price,
                high=close_price + 20,
                low=open_price - 20,
                close=close_price,
                volume=100 + i,
                timestamp=f'2026-01-01T{i:02d}:00:00Z',
            )
        )

    result = MarketRegimeClassifier().classify(candles)
    assert result['regime'] in {'trend_up', 'trend_down', 'sideways', 'uncertain'}
    assert result['volatility_state'] in {'low', 'normal', 'high'}
    assert result['higher_tf_bias'] in {'bullish', 'bearish', 'neutral'}
    assert 'trend_gap_pct' in result
    assert 'range_pct' in result
    assert 'momentum_pct' in result


def test_trading_cycle_route_block_reason_for_trend_strategy_on_ranging():
    from investment_bot.risk.controller import RiskController
    from investment_bot.services.trading_cycle import TradingCycleService

    broker = PaperBroker(starting_cash=100000.0, ledger_store=None, min_order_notional=5000.0)
    service = TradingCycleService(risk_controller=RiskController(), paper_broker=broker)
    assert service._route_block_reason('trend_following', {'regime': 'ranging'}) == 'trend_strategy_route_blocked'


def test_trading_cycle_route_block_reason_for_mean_reversion_on_uptrend():
    from investment_bot.risk.controller import RiskController
    from investment_bot.services.trading_cycle import TradingCycleService

    broker = PaperBroker(starting_cash=100000.0, ledger_store=None, min_order_notional=5000.0)
    service = TradingCycleService(risk_controller=RiskController(), paper_broker=broker)
    assert service._route_block_reason('mean_reversion', {'regime': 'uptrend'}) == 'range_strategy_route_blocked'


def test_trading_cycle_route_block_reason_for_uncertain_regime():
    from investment_bot.risk.controller import RiskController
    from investment_bot.services.trading_cycle import TradingCycleService

    broker = PaperBroker(starting_cash=100000.0, ledger_store=None, min_order_notional=5000.0)
    service = TradingCycleService(risk_controller=RiskController(), paper_broker=broker)
    assert service._route_block_reason('trend_following', {'regime': 'mixed'}) == 'uncertain_regime_blocked'


def test_risk_controller_blocks_buy_on_bearish_higher_tf_bias(monkeypatch):
    from investment_bot.models.signal import TradeSignal
    from investment_bot.risk.controller import RiskController
    from investment_bot.core.settings import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    monkeypatch.setattr(settings, 'blocked_hours', [])
    monkeypatch.setattr(settings, 'higher_tf_bias_filter_enabled', True)
    signal = TradeSignal(strategy_name='trend_following', symbol='BTC/KRW', action='buy', confidence=0.8, reason='test')
    signal.meta = {'higher_tf_bias': 'bearish', 'volatility_state': 'normal', 'losing_streak': 0}
    review = RiskController(min_order_notional=5000, base_entry_notional=10000).review(signal, cash_balance=100000, latest_price=10000)
    assert review['approved'] is False
    assert 'higher_tf_bias_mismatch' in review['reason']


def test_risk_controller_reduces_size_on_high_volatility_and_losing_streak(monkeypatch):
    from investment_bot.models.signal import TradeSignal
    from investment_bot.risk.controller import RiskController
    from investment_bot.core.settings import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    monkeypatch.setattr(settings, 'blocked_hours', [])
    signal = TradeSignal(strategy_name='trend_following', symbol='BTC/KRW', action='buy', confidence=1.0, reason='test')
    signal.meta = {'higher_tf_bias': 'bullish', 'volatility_state': 'high', 'losing_streak': 3}
    review = RiskController(min_order_notional=5000, base_entry_notional=10000).review(signal, cash_balance=100000, latest_price=10000)
    assert review['approved'] is True
    assert review['risk_mode'] == 'reduced'
    assert review['size_scale'] > 0
    assert review['target_notional'] <= 5000


def test_paper_broker_tracks_losing_streak_on_loss(tmp_path):
    ledger_path = tmp_path / 'ledger.json'
    broker = PaperBroker(starting_cash=100000.0, ledger_store=LedgerStore(str(ledger_path)), min_order_notional=5000.0)
    broker.submit(
        reviewed_signal={
            'strategy_name': 'trend_following', 'symbol': 'BTC/KRW', 'action': 'buy',
            'confidence': 0.8, 'size_scale': 1.0, 'reason': 'entry', 'strategy_version': 'v1.0-base'
        },
        execution_price=10000.0,
    )
    broker.submit(
        reviewed_signal={
            'strategy_name': 'trend_following', 'symbol': 'BTC/KRW', 'action': 'sell',
            'confidence': 0.8, 'size_scale': 1.0, 'reason': 'exit', 'strategy_version': 'v1.0-base'
        },
        execution_price=9000.0,
    )
    assert broker.losing_streak == 1
    state = broker.export_state()
    assert state['losing_streak'] == 1


def test_paper_broker_sets_exit_rule_metadata_on_buy(tmp_path):
    ledger_path = tmp_path / 'ledger.json'
    broker = PaperBroker(starting_cash=100000.0, ledger_store=LedgerStore(str(ledger_path)), min_order_notional=5000.0)
    broker.submit(
        reviewed_signal={
            'strategy_name': 'trend_following', 'symbol': 'BTC/KRW', 'action': 'buy',
            'confidence': 0.8, 'size_scale': 1.0, 'reason': 'entry', 'strategy_version': 'v1.0-base'
        },
        execution_price=10000.0,
    )
    pos = broker.positions['BTC/KRW']
    assert pos['stop_price'] is not None
    assert pos['tp1_price'] is not None
    assert pos['tp1_done'] is False


def test_paper_broker_partial_take_profit_trigger(tmp_path):
    ledger_path = tmp_path / 'ledger.json'
    broker = PaperBroker(starting_cash=100000.0, ledger_store=LedgerStore(str(ledger_path)), min_order_notional=5000.0)
    broker.submit(
        reviewed_signal={
            'strategy_name': 'trend_following', 'symbol': 'BTC/KRW', 'action': 'buy',
            'confidence': 0.8, 'size_scale': 2.0, 'reason': 'entry', 'strategy_version': 'v1.0-base'
        },
        execution_price=10000.0,
    )
    result = broker.evaluate_exit_rules('BTC/KRW', market_price=10350.0)
    assert result['status'] == 'triggered'
    assert result['reason'] == 'partial_take_profit'
    assert result['size_scale'] == 1.0
    pos = broker.positions['BTC/KRW']
    assert pos['trailing_active'] is True
    assert pos['trailing_stop_price'] == 10246.5


def test_paper_broker_tp1_sells_full_position_when_partial_is_below_min_order(tmp_path, monkeypatch):
    from investment_bot.core.settings import get_settings

    monkeypatch.setenv("INVESTMENT_BOT_CONFIG_PATH", "config/dev.yml")
    get_settings.cache_clear()
    ledger_path = tmp_path / 'ledger.json'
    broker = PaperBroker(starting_cash=100000.0, ledger_store=LedgerStore(str(ledger_path)), min_order_notional=5000.0)
    broker.submit(
        reviewed_signal={
            'strategy_name': 'trend_following', 'symbol': 'BTC/KRW', 'action': 'buy',
            'confidence': 0.8, 'size_scale': 10.0, 'reason': 'entry', 'strategy_version': 'v1.0-dev'
        },
        execution_price=1000.0,
    )

    result = broker.evaluate_exit_rules('BTC/KRW', market_price=1016.0)

    assert result['status'] == 'triggered'
    assert result['reason'] == 'partial_take_profit'
    assert result['size_scale'] == broker.positions['BTC/KRW']['quantity']
    get_settings.cache_clear()


def test_paper_broker_trailing_stop_trigger(tmp_path):
    from datetime import datetime, timezone
    ledger_path = tmp_path / 'ledger.json'
    broker = PaperBroker(starting_cash=100000.0, ledger_store=LedgerStore(str(ledger_path)), min_order_notional=5000.0)
    broker.submit(
        reviewed_signal={
            'strategy_name': 'trend_following', 'symbol': 'BTC/KRW', 'action': 'buy',
            'confidence': 0.8, 'size_scale': 1.0, 'reason': 'entry', 'strategy_version': 'v1.0-base'
        },
        execution_price=10000.0,
    )
    broker.evaluate_exit_rules('BTC/KRW', market_price=10300.0, now=datetime.now(timezone.utc))
    result = broker.evaluate_exit_rules('BTC/KRW', market_price=10150.0, now=datetime.now(timezone.utc))
    assert result['status'] == 'triggered'
    assert result['reason'] == 'trailing_stop'


def test_paper_broker_timeout_exit_trigger(tmp_path):
    from datetime import datetime, timedelta, timezone
    ledger_path = tmp_path / 'ledger.json'
    broker = PaperBroker(starting_cash=100000.0, ledger_store=LedgerStore(str(ledger_path)), min_order_notional=5000.0)
    broker.submit(
        reviewed_signal={
            'strategy_name': 'trend_following', 'symbol': 'BTC/KRW', 'action': 'buy',
            'confidence': 0.8, 'size_scale': 1.0, 'reason': 'entry', 'strategy_version': 'v1.0-base'
        },
        execution_price=10000.0,
    )
    broker.positions['BTC/KRW']['opened_at'] = (datetime.now(timezone.utc) - timedelta(minutes=120)).isoformat().replace('+00:00', 'Z')
    result = broker.evaluate_exit_rules('BTC/KRW', market_price=10020.0, now=datetime.now(timezone.utc))
    assert result['status'] == 'triggered'
    assert result['reason'] == 'timeout'


def test_standard_backtest_returns_config_snapshot():
    from investment_bot.services.backtest_service import BacktestService

    class FakeReplayAdapter:
        def __init__(self):
            self._cursor = {}

    class FakeMarketDataService:
        def __init__(self):
            self.registry = {'replay': FakeReplayAdapter()}
        def get_recent_candles(self, adapter_name, symbol, timeframe, limit):
            from investment_bot.models.market import Candle
            return [
                Candle(symbol=symbol, timeframe=timeframe, open=100, high=110, low=90, close=100 + i, volume=1, timestamp=f'2026-01-01T00:0{i}:00Z')
                for i in range(limit)
            ]
        def advance_replay(self, symbol, timeframe, steps):
            return None

    class FakeTradingCycleService:
        def run(self, strategy_name, candles):
            return {
                'signal': {'action': 'hold'},
                'review': {'approved': False},
                'portfolio': {'total_equity': 100000.0},
            }

    broker = PaperBroker(starting_cash=100000.0, ledger_store=None, min_order_notional=5000.0)
    service = BacktestService(
        market_data_service=FakeMarketDataService(),
        paper_broker=broker,
        trading_cycle_service=FakeTradingCycleService(),
        metrics_service=__import__('investment_bot.services.metrics_service', fromlist=['MetricsService']).MetricsService(),
    )
    result = service.run_standard_backtest('trend_following', 'BTC/KRW', '1h', 5, 2)
    assert 'run_id' in result
    assert result['config_snapshot']['strategy_name'] == 'trend_following'
    assert result['config_snapshot']['fee_model'] == 'paper_broker_fee_pct'


def test_walkforward_returns_segment_results():
    from investment_bot.services.backtest_service import BacktestService
    from investment_bot.services.metrics_service import MetricsService

    class FakeReplayAdapter:
        def __init__(self):
            self._cursor = {}

    class FakeMarketDataService:
        def __init__(self):
            self.registry = {'replay': FakeReplayAdapter()}
        def get_recent_candles(self, adapter_name, symbol, timeframe, limit):
            from investment_bot.models.market import Candle
            return [
                Candle(symbol=symbol, timeframe=timeframe, open=100, high=110, low=90, close=100 + i, volume=1, timestamp=f'2026-01-01T00:0{i}:00Z')
                for i in range(limit)
            ]
        def advance_replay(self, symbol, timeframe, steps):
            return None

    class FakeTradingCycleService:
        def run(self, strategy_name, candles):
            return {'signal': {'action': 'hold'}, 'review': {'approved': False}, 'portfolio': {'total_equity': 100000.0, 'total_realized_pnl': 0.0, 'total_unrealized_pnl': 0.0, 'order_count': 0}}

    broker = PaperBroker(starting_cash=100000.0, ledger_store=None, min_order_notional=5000.0)
    service = BacktestService(FakeMarketDataService(), broker, FakeTradingCycleService(), MetricsService())
    result = service.run_walkforward('trend_following', 'BTC/KRW', '1h', 5, train_steps=10, test_steps=2, segments=3)
    assert result['segments'] == 3
    assert len(result['results']) == 3


def test_paper_compare_service_returns_summary():
    from investment_bot.services.paper_compare_service import PaperCompareService
    result = PaperCompareService().compare(
        backtest_trades=[{'entry_price': 100.0, 'net_pnl': 10.0}, {'entry_price': 110.0, 'net_pnl': -5.0}],
        paper_trades=[{'entry_price': 101.0, 'net_pnl': 9.0}],
    )
    assert result['matched_count'] == 1
    assert result['missed_trade_count'] == 1
    assert result['avg_fill_price_diff'] == 1.0


def test_live_deploy_checklist_reports_completion():
    from investment_bot.services.live_deploy_checklist_service import LiveDeployChecklistService
    result = LiveDeployChecklistService().build(
        version='v1.2.0',
        completed={
            'backtest_completed': True,
            'out_of_sample_checked': True,
            'walkforward_checked': True,
            'paper_trading_checked': True,
            'fees_and_slippage_checked': True,
            'max_loss_checked': True,
            'feature_flag_ready': True,
            'rollback_ready': True,
        },
        approver='mk',
    )
    assert result['deploy_candidate_version'] == 'v1.2.0'
    assert result['all_completed'] is True
    assert result['approver'] == 'mk'


def test_auto_trade_service_skips_when_krw_balance_is_below_threshold(tmp_path):
    shadow = FakeShadowService()
    service = make_service(tmp_path, Settings(symbols=["BTC/KRW"], auto_trade_min_krw_balance=15000, auto_trade_target_allocation_pct=20, auto_trade_meaningful_order_notional=10000), shadow, FakeAccountService(krw_cash=5000))
    result = service.run_once()
    assert result['status'] == 'skipped'
    assert result['reason'] == 'insufficient_krw_balance'


def test_auto_trade_service_submits_buy_when_profile_conditions_are_met(tmp_path):
    shadow = FakeShadowService({
        ("BTC/KRW", "trend_following"): {"action": "buy", "latest_price": 1000.0, "confidence": 0.5, "target_notional": 6000.0, "market_regime": {"regime": "uptrend"}},
        ("BTC/KRW", "mean_reversion"): {"action": "hold", "latest_price": 1000.0, "confidence": 0.1, "target_notional": 0.0, "market_regime": {"regime": "uptrend"}},
        ("BTC/KRW", "dca"): {"action": "hold", "latest_price": 1000.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "uptrend"}},
    })
    service = make_service(tmp_path, Settings(symbols=["BTC/KRW"], auto_trade_min_krw_balance=15000, auto_trade_target_allocation_pct=20, auto_trade_meaningful_order_notional=5000, min_order_notional=5000), shadow, FakeAccountService(krw_cash=55000))
    result = service.run_once()
    assert result['status'] == 'submitted'
    assert result['side'] == 'buy'
    assert result['submit']['volume'] == 6.0


def test_auto_trade_service_caps_buy_by_review_target_notional(tmp_path):
    shadow = FakeShadowService({
        ("BTC/KRW", "trend_following"): {"action": "buy", "latest_price": 1000.0, "confidence": 0.5, "target_notional": 5200.0, "market_regime": {"regime": "uptrend"}},
        ("BTC/KRW", "mean_reversion"): {"action": "hold", "latest_price": 1000.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "uptrend"}},
        ("BTC/KRW", "dca"): {"action": "hold", "latest_price": 1000.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "uptrend"}},
    })
    service = make_service(tmp_path, Settings(symbols=["BTC/KRW"], auto_trade_min_krw_balance=15000, auto_trade_target_allocation_pct=20, auto_trade_meaningful_order_notional=5000, min_order_notional=5000), shadow, FakeAccountService(krw_cash=100000))
    result = service.run_once()
    assert result['status'] == 'submitted'
    assert result['submit']['volume'] == 5.2


def test_auto_trade_service_skips_unexecutable_top_scored_buy_for_next_buy(tmp_path):
    shadow = FakeShadowService({
        ("BTC/KRW", "trend_following"): {"action": "buy", "latest_price": 1000.0, "confidence": 0.9, "target_notional": 4000.0, "market_regime": {"regime": "uptrend"}},
        ("BTC/KRW", "mean_reversion"): {"action": "hold", "latest_price": 1000.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "uptrend"}},
        ("BTC/KRW", "dca"): {"action": "hold", "latest_price": 1000.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "uptrend"}},
        ("ETH/KRW", "trend_following"): {"action": "buy", "latest_price": 1000.0, "confidence": 0.5, "target_notional": 6000.0, "market_regime": {"regime": "uptrend"}},
        ("ETH/KRW", "mean_reversion"): {"action": "hold", "latest_price": 1000.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "uptrend"}},
        ("ETH/KRW", "dca"): {"action": "hold", "latest_price": 1000.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "uptrend"}},
    })
    service = make_service(
        tmp_path,
        Settings(symbols=["BTC/KRW", "ETH/KRW"], auto_trade_min_krw_balance=10000, auto_trade_target_allocation_pct=20, auto_trade_meaningful_order_notional=5000, min_order_notional=5000),
        shadow,
        FakeAccountService(krw_cash=100000),
    )
    result = service.run_once()
    assert result["status"] == "submitted"
    assert result["symbol"] == "ETH/KRW"
    assert result["side"] == "buy"
    assert result["submit"]["volume"] == 6.0


def test_auto_trade_service_evaluates_configured_dynamic_top_n(tmp_path):
    symbols = [f"SYM{i}/KRW" for i in range(12)]
    by_symbol_strategy = {}
    for symbol in symbols:
        action = "buy" if symbol == "SYM11/KRW" else "hold"
        confidence = 0.9 if action == "buy" else 0.0
        target_notional = 6000.0 if action == "buy" else 0.0
        by_symbol_strategy[(symbol, "trend_following")] = {
            "action": action,
            "latest_price": 1000.0,
            "confidence": confidence,
            "target_notional": target_notional,
            "market_regime": {"regime": "uptrend"},
        }
        by_symbol_strategy[(symbol, "mean_reversion")] = {
            "action": "hold",
            "latest_price": 1000.0,
            "confidence": 0.0,
            "target_notional": 0.0,
            "market_regime": {"regime": "uptrend"},
        }
        by_symbol_strategy[(symbol, "dca")] = {
            "action": "hold",
            "latest_price": 1000.0,
            "confidence": 0.0,
            "target_notional": 0.0,
            "market_regime": {"regime": "uptrend"},
        }
    service = make_service(
        tmp_path,
        Settings(
            symbols=symbols,
            dynamic_symbol_selection=True,
            dynamic_symbol_top_n=12,
            auto_trade_min_krw_balance=15000,
            auto_trade_target_allocation_pct=20,
            auto_trade_meaningful_order_notional=5000,
            min_order_notional=5000,
        ),
        FakeShadowService(by_symbol_strategy),
        FakeAccountService(krw_cash=50000),
    )
    service.dynamic_symbol_selector = FakeDynamicSymbolSelector()

    result = service.run_once()

    assert service._last_selected_symbols == symbols
    assert result["status"] == "submitted"
    assert result["symbol"] == "SYM11/KRW"
    assert result["side"] == "buy"


def test_auto_trade_service_enforces_total_exposure_limit_before_buy(tmp_path):
    shadow = FakeShadowService({
        ("BTC/KRW", "trend_following"): {"action": "buy", "latest_price": 1000.0, "confidence": 0.7, "target_notional": 10000.0, "market_regime": {"regime": "uptrend"}},
        ("BTC/KRW", "mean_reversion"): {"action": "hold", "latest_price": 1000.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "uptrend"}},
        ("BTC/KRW", "dca"): {"action": "hold", "latest_price": 1000.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "uptrend"}},
    })
    service = make_service(tmp_path, Settings(symbols=["BTC/KRW"], auto_trade_min_krw_balance=15000, auto_trade_target_allocation_pct=20, auto_trade_meaningful_order_notional=5000, min_order_notional=5000, auto_trade_max_total_exposure_pct=60.0), shadow, FakeAccountService(krw_cash=20000, asset_balances={"ETH/KRW": 0.5}, avg_buy_prices={"ETH/KRW": 100000.0}))
    result = service.run_once()
    assert result['status'] == 'skipped'
    assert result['reason'] == 'below_meaningful_order_notional_or_total_exposure_limit'
    assert result['blocker'] == 'total_exposure_limit'
    assert result['remaining_exposure_room'] == 0.0


def test_auto_trade_service_enforces_symbol_exposure_limit_before_buy(tmp_path):
    shadow = FakeShadowService({
        ("BTC/KRW", "trend_following"): {"action": "buy", "latest_price": 1000.0, "confidence": 0.7, "target_notional": 10000.0, "market_regime": {"regime": "uptrend"}},
        ("BTC/KRW", "mean_reversion"): {"action": "hold", "latest_price": 1000.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "uptrend"}},
        ("BTC/KRW", "dca"): {"action": "hold", "latest_price": 1000.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "uptrend"}},
    })
    service = make_service(
        tmp_path,
        Settings(
            symbols=["BTC/KRW"],
            auto_trade_min_krw_balance=10000,
            auto_trade_target_allocation_pct=20,
            auto_trade_meaningful_order_notional=5000,
            min_order_notional=5000,
            max_symbol_exposure_pct=20.0,
            auto_trade_max_total_exposure_pct=50.0,
        ),
        shadow,
        FakeAccountService(krw_cash=81000, asset_balances={"BTC/KRW": 19.0}, avg_buy_prices={"BTC/KRW": 1000.0}),
    )
    result = service.run_once()
    assert result['status'] == 'skipped'
    assert result['reason'] == 'below_meaningful_order_notional_or_total_exposure_limit'
    assert result['blocker'] == 'symbol_exposure_limit'
    assert result['symbol_exposure'] == 19000.0
    assert result['remaining_symbol_room'] == 1000.0


def test_dynamic_symbol_selection_keeps_held_symbol_for_stop_loss(tmp_path):
    shadow = FakeShadowService({
        ("BTC/KRW", "trend_following"): {"action": "buy", "latest_price": 1000.0, "confidence": 0.7, "target_notional": 10000.0, "market_regime": {"regime": "uptrend"}},
        ("BTC/KRW", "mean_reversion"): {"action": "hold", "latest_price": 1000.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "uptrend"}},
        ("BTC/KRW", "dca"): {"action": "hold", "latest_price": 1000.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "uptrend"}},
        ("ETH/KRW", "trend_following"): {"action": "hold", "latest_price": 970.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "downtrend"}},
        ("ETH/KRW", "mean_reversion"): {"action": "hold", "latest_price": 970.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "downtrend"}},
        ("ETH/KRW", "dca"): {"action": "hold", "latest_price": 970.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "downtrend"}},
    })
    service = make_service(
        tmp_path,
        Settings(
            symbols=["BTC/KRW", "ETH/KRW"],
            dynamic_symbol_selection=True,
            dynamic_symbol_top_n=1,
            auto_trade_min_krw_balance=10000,
            auto_trade_target_allocation_pct=20,
            auto_trade_meaningful_order_notional=5000,
            auto_trade_min_managed_position_notional=5000.0,
            auto_trade_stop_loss_pct=1.5,
            min_order_notional=5000,
        ),
        shadow,
        FakeAccountService(krw_cash=50000, asset_balances={"ETH/KRW": 10.0}, avg_buy_prices={"ETH/KRW": 1000.0}),
    )
    service.dynamic_symbol_selector = FixedDynamicSymbolSelector(["BTC/KRW"])

    result = service.run_once()

    assert service._last_selected_symbols == ["BTC/KRW", "ETH/KRW"]
    assert result["status"] == "submitted"
    assert result["symbol"] == "ETH/KRW"
    assert result["side"] == "sell"
    assert result["override"]["override_reason"] == "stop_loss"


def test_auto_trade_service_prefers_sell_over_buy_across_symbols(tmp_path):
    shadow = FakeShadowService({
        ("BTC/KRW", "trend_following"): {"action": "buy", "latest_price": 1000.0, "confidence": 0.9, "target_notional": 6000.0, "market_regime": {"regime": "uptrend"}},
        ("BTC/KRW", "mean_reversion"): {"action": "hold", "latest_price": 1000.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "uptrend"}},
        ("BTC/KRW", "dca"): {"action": "hold", "latest_price": 1000.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "uptrend"}},
        ("ETH/KRW", "trend_following"): {"action": "hold", "latest_price": 2000.0, "confidence": 0.1, "target_notional": 0.0, "market_regime": {"regime": "downtrend"}},
        ("ETH/KRW", "mean_reversion"): {"action": "sell", "latest_price": 2000.0, "confidence": 0.4, "target_notional": 0.0, "market_regime": {"regime": "downtrend"}},
        ("ETH/KRW", "dca"): {"action": "hold", "latest_price": 2000.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "downtrend"}},
    })
    service = make_service(tmp_path, Settings(symbols=["BTC/KRW", "ETH/KRW"], auto_trade_min_managed_position_notional=10000.0), shadow, FakeAccountService(krw_cash=50000, asset_balances={"ETH/KRW": 10.0}, avg_buy_prices={"ETH/KRW": 2000.0}))
    result = service.run_once()
    assert result['status'] == 'submitted'
    assert result['symbol'] == 'ETH/KRW'
    assert result['side'] == 'sell'


def test_auto_trade_service_prefers_stronger_executable_buy_over_weak_sell(tmp_path):
    shadow = FakeShadowService({
        ("BTC/KRW", "trend_following"): {"action": "buy", "latest_price": 1000.0, "confidence": 0.7, "target_notional": 10000.0, "market_regime": {"regime": "uptrend"}},
        ("BTC/KRW", "mean_reversion"): {"action": "hold", "latest_price": 1000.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "uptrend"}},
        ("BTC/KRW", "dca"): {"action": "hold", "latest_price": 1000.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "uptrend"}},
        ("ETH/KRW", "trend_following"): {"action": "hold", "latest_price": 2000.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "downtrend"}},
        ("ETH/KRW", "mean_reversion"): {"action": "sell", "latest_price": 2000.0, "confidence": 0.2, "target_notional": 0.0, "market_regime": {"regime": "downtrend"}},
        ("ETH/KRW", "dca"): {"action": "hold", "latest_price": 2000.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "downtrend"}},
    })
    service = make_service(
        tmp_path,
        Settings(
            symbols=["BTC/KRW", "ETH/KRW"],
            auto_trade_min_krw_balance=10000,
            auto_trade_target_allocation_pct=20,
            auto_trade_meaningful_order_notional=5000,
            min_order_notional=5000,
            auto_trade_min_managed_position_notional=5000.0,
        ),
        shadow,
        FakeAccountService(krw_cash=50000, asset_balances={"ETH/KRW": 5.0}, avg_buy_prices={"ETH/KRW": 2000.0}),
    )
    result = service.run_once()
    assert result['status'] == 'submitted'
    assert result['symbol'] == 'BTC/KRW'
    assert result['side'] == 'buy'
    assert result['submit']['volume'] == 10.0


def test_auto_trade_service_ignores_unactionable_sell_when_buy_candidate_exists(tmp_path):
    shadow = FakeShadowService({
        ("BTC/KRW", "trend_following"): {"action": "buy", "latest_price": 1000.0, "confidence": 0.9, "target_notional": 6000.0, "market_regime": {"regime": "uptrend"}},
        ("BTC/KRW", "mean_reversion"): {"action": "hold", "latest_price": 1000.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "uptrend"}},
        ("BTC/KRW", "dca"): {"action": "hold", "latest_price": 1000.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "uptrend"}},
        ("ETH/KRW", "trend_following"): {"action": "sell", "latest_price": 2000.0, "confidence": 0.9, "target_notional": 0.0, "market_regime": {"regime": "downtrend"}},
        ("ETH/KRW", "mean_reversion"): {"action": "hold", "latest_price": 2000.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "downtrend"}},
        ("ETH/KRW", "dca"): {"action": "hold", "latest_price": 2000.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "downtrend"}},
    })
    service = make_service(
        tmp_path,
        Settings(symbols=["BTC/KRW", "ETH/KRW"], min_order_notional=5000, auto_trade_meaningful_order_notional=5000, auto_trade_min_managed_position_notional=1500.0),
        shadow,
        FakeAccountService(krw_cash=50000, asset_balances={"ETH/KRW": 1.0}, avg_buy_prices={"ETH/KRW": 2000.0}),
    )
    result = service.run_once()
    assert result['status'] == 'submitted'
    assert result['symbol'] == 'BTC/KRW'
    assert result['side'] == 'buy'


def test_auto_trade_service_submits_sell_using_exchange_balance(tmp_path):
    shadow = FakeShadowService({
        ("BTC/KRW", "trend_following"): {"action": "sell", "latest_price": 1000.0, "confidence": 0.8, "target_notional": 0.0, "market_regime": {"regime": "downtrend"}},
        ("BTC/KRW", "mean_reversion"): {"action": "hold", "latest_price": 1000.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "downtrend"}},
        ("BTC/KRW", "dca"): {"action": "hold", "latest_price": 1000.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "downtrend"}},
    })
    service = make_service(tmp_path, Settings(symbols=["BTC/KRW"], auto_trade_min_krw_balance=15000, auto_trade_target_allocation_pct=20, auto_trade_meaningful_order_notional=10000, min_order_notional=5000, auto_trade_min_managed_position_notional=100.0), shadow, FakeAccountService(krw_cash=0, asset_balances={"BTC/KRW": 0.25}, avg_buy_prices={"BTC/KRW": 900.0}))
    result = service.run_once()
    assert result['status'] == 'submitted'
    assert result['side'] == 'sell'
    assert result['submit']['volume'] == 0.2


def test_auto_trade_service_sell_does_not_cool_down_next_buy(tmp_path):
    sell_shadow = FakeShadowService({
        ("BTC/KRW", "trend_following"): {"action": "sell", "latest_price": 1000.0, "confidence": 0.8, "target_notional": 0.0, "market_regime": {"regime": "downtrend"}},
        ("BTC/KRW", "mean_reversion"): {"action": "hold", "latest_price": 1000.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "downtrend"}},
        ("BTC/KRW", "dca"): {"action": "hold", "latest_price": 1000.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "downtrend"}},
    })
    service = make_service(
        tmp_path,
        Settings(symbols=["BTC/KRW"], auto_trade_cooldown_cycles=1, min_order_notional=5000, auto_trade_min_managed_position_notional=100.0),
        sell_shadow,
        FakeAccountService(krw_cash=50000, asset_balances={"BTC/KRW": 6.0}, avg_buy_prices={"BTC/KRW": 1000.0}),
    )

    first = service.run_once()
    service.shadow_service = FakeShadowService({
        ("BTC/KRW", "trend_following"): {"action": "buy", "latest_price": 1000.0, "confidence": 0.9, "target_notional": 10000.0, "market_regime": {"regime": "uptrend"}},
        ("BTC/KRW", "mean_reversion"): {"action": "hold", "latest_price": 1000.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "uptrend"}},
        ("BTC/KRW", "dca"): {"action": "hold", "latest_price": 1000.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "uptrend"}},
    })
    service.account_service = FakeAccountService(krw_cash=50000, asset_balances={}, avg_buy_prices={})

    second = service.run_once()

    assert first["status"] == "submitted"
    assert first["side"] == "sell"
    assert second["status"] == "submitted"
    assert second["side"] == "buy"


def test_auto_trade_service_sells_full_position_when_partial_sell_is_below_min_order(tmp_path):
    shadow = FakeShadowService({
        ("BTC/KRW", "trend_following"): {"action": "sell", "latest_price": 1000.0, "confidence": 0.5, "target_notional": 0.0, "market_regime": {"regime": "downtrend"}},
        ("BTC/KRW", "mean_reversion"): {"action": "hold", "latest_price": 1000.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "downtrend"}},
        ("BTC/KRW", "dca"): {"action": "hold", "latest_price": 1000.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "downtrend"}},
    })
    service = make_service(tmp_path, Settings(symbols=["BTC/KRW"], min_order_notional=5000, auto_trade_min_managed_position_notional=1500.0), shadow, FakeAccountService(krw_cash=0, asset_balances={"BTC/KRW": 8.0}, avg_buy_prices={"BTC/KRW": 1000.0}))
    result = service.run_once()
    assert result['status'] == 'submitted'
    assert result['side'] == 'sell'
    assert result['submit']['volume'] == 8.0


def test_auto_trade_service_skips_dust_positions_below_min_managed_notional(tmp_path):
    shadow = FakeShadowService({
        ("SOL/KRW", "trend_following"): {"action": "sell", "latest_price": 132800.0, "confidence": 0.4, "target_notional": 0.0, "market_regime": {"regime": "downtrend"}},
        ("SOL/KRW", "mean_reversion"): {"action": "hold", "latest_price": 132800.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "downtrend"}},
        ("SOL/KRW", "dca"): {"action": "hold", "latest_price": 132800.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "downtrend"}},
    })
    service = make_service(tmp_path, Settings(symbols=["SOL/KRW"], auto_trade_min_managed_position_notional=10000.0), shadow, FakeAccountService(krw_cash=0, asset_balances={"SOL/KRW": 0.00007428}, avg_buy_prices={"SOL/KRW": 257501.2175}))
    result = service.run_once()
    assert result['status'] == 'skipped'
    assert result['reason'] == 'non_actionable_signal'


def test_auto_trade_service_reports_managed_notional_when_sell_is_blocked_by_threshold(tmp_path):
    shadow = FakeShadowService({
        ("SEI/KRW", "trend_following"): {"action": "sell", "latest_price": 78.8, "confidence": 0.99, "target_notional": 0.0, "market_regime": {"regime": "downtrend"}},
        ("SEI/KRW", "mean_reversion"): {"action": "hold", "latest_price": 78.8, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "downtrend"}},
        ("SEI/KRW", "dca"): {"action": "hold", "latest_price": 78.8, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "downtrend"}},
    })
    service = make_service(
        tmp_path,
        Settings(symbols=["SEI/KRW"], auto_trade_min_managed_position_notional=10000.0),
        shadow,
        FakeAccountService(krw_cash=0, asset_balances={"SEI/KRW": 121.65450122}, avg_buy_prices={"SEI/KRW": 82.1}),
    )
    result = service.run_once()
    assert result['status'] == 'skipped'
    assert result['reason'] == 'non_actionable_signal'
    assert result['top_hold_candidates'] == []


def test_auto_trade_service_logs_hold_summary_when_all_candidates_are_non_actionable(tmp_path, caplog):
    shadow = FakeShadowService({
        ("BTC/KRW", "trend_following"): {"action": "hold", "latest_price": 1000.0, "confidence": 0.12, "target_notional": 0.0, "market_regime": {"regime": "mixed"}},
        ("BTC/KRW", "mean_reversion"): {"action": "hold", "latest_price": 1000.0, "confidence": 0.34, "target_notional": 0.0, "market_regime": {"regime": "mixed"}},
        ("BTC/KRW", "dca"): {"action": "hold", "latest_price": 1000.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "mixed"}},
    })
    service = make_service(tmp_path, Settings(symbols=["BTC/KRW"]), shadow, FakeAccountService(krw_cash=50000))
    with caplog.at_level(logging.INFO):
        result = service.run_once()
    assert result["status"] == "skipped"
    assert result["reason"] == "non_actionable_signal"
    assert result["top_hold_candidates"] == []
    assert "top_hold_candidates" not in caplog.text


def test_auto_trade_service_stop_loss_uses_price_pct_not_quantity(tmp_path):
    shadow = FakeShadowService({
        ("BTC/KRW", "trend_following"): {"action": "hold", "latest_price": 98000.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "uptrend"}},
        ("BTC/KRW", "mean_reversion"): {"action": "hold", "latest_price": 98000.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "uptrend"}},
        ("BTC/KRW", "dca"): {"action": "hold", "latest_price": 98000.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "uptrend"}},
    })
    service = make_service(tmp_path, Settings(symbols=["BTC/KRW"], auto_trade_stop_loss_pct=1.5, auto_trade_partial_take_profit_pct=2.0, auto_trade_trailing_stop_pct=1.0, auto_trade_partial_sell_ratio=0.5, auto_trade_min_managed_position_notional=10.0), shadow, FakeAccountService(krw_cash=0.0, asset_balances={"BTC/KRW": 0.00060394}, avg_buy_prices={"BTC/KRW": 100000.0}))
    result = service.run_once()
    assert result['status'] == 'submitted'
    assert result['override']['override_reason'] == 'stop_loss'
    assert result['submit']['volume'] == 0.00060394


def test_auto_trade_service_take_profit_trailing_stop_with_small_btc_quantity(tmp_path):
    shadow = FakeShadowService({
        ("BTC/KRW", "trend_following"): {"action": "hold", "latest_price": 102000.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "uptrend"}},
        ("BTC/KRW", "mean_reversion"): {"action": "hold", "latest_price": 102000.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "uptrend"}},
        ("BTC/KRW", "dca"): {"action": "hold", "latest_price": 102000.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "uptrend"}},
    })
    service = make_service(tmp_path, Settings(symbols=["BTC/KRW"], auto_trade_stop_loss_pct=1.5, auto_trade_partial_take_profit_pct=2.0, auto_trade_trailing_stop_pct=1.0, auto_trade_partial_sell_ratio=0.5, auto_trade_min_managed_position_notional=10.0), shadow, FakeAccountService(krw_cash=0.0, asset_balances={"BTC/KRW": 0.00060394}, avg_buy_prices={"BTC/KRW": 100000.0}))
    service._peak_price_by_symbol['BTC/KRW'] = 103500.0
    result = service.run_once()
    assert result['status'] == 'submitted'
    assert result['override']['override_reason'] == 'take_profit_trailing_stop'
    assert result['submit']['volume'] == 0.00030197


def test_auto_trade_service_trailing_profit_uses_peak_activation_after_pullback(tmp_path):
    shadow = FakeShadowService({
        ("BTC/KRW", "trend_following"): {"action": "hold", "latest_price": 101400.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "uptrend"}},
        ("BTC/KRW", "mean_reversion"): {"action": "hold", "latest_price": 101400.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "uptrend"}},
        ("BTC/KRW", "dca"): {"action": "hold", "latest_price": 101400.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "uptrend"}},
    })
    service = make_service(tmp_path, Settings(symbols=["BTC/KRW"], auto_trade_stop_loss_pct=1.5, auto_trade_partial_take_profit_pct=2.0, auto_trade_trailing_stop_pct=1.0, auto_trade_partial_sell_ratio=0.5, auto_trade_min_managed_position_notional=10.0), shadow, FakeAccountService(krw_cash=0.0, asset_balances={"BTC/KRW": 0.00060394}, avg_buy_prices={"BTC/KRW": 100000.0}))
    service._peak_price_by_symbol['BTC/KRW'] = 103500.0

    result = service.run_once()

    assert result['status'] == 'submitted'
    assert result['override']['override_reason'] == 'take_profit_trailing_stop'
    assert result['submit']['volume'] == 0.00030197


def test_auto_trade_service_prioritizes_stop_loss_override_over_trailing_profit(tmp_path):
    shadow = FakeShadowService({
        ("BTC/KRW", "trend_following"): {"action": "hold", "latest_price": 1020.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "trend_up"}},
        ("BTC/KRW", "mean_reversion"): {"action": "hold", "latest_price": 1020.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "trend_up"}},
        ("BTC/KRW", "dca"): {"action": "hold", "latest_price": 1020.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "trend_up"}},
        ("ETH/KRW", "trend_following"): {"action": "hold", "latest_price": 970.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "trend_down"}},
        ("ETH/KRW", "mean_reversion"): {"action": "hold", "latest_price": 970.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "trend_down"}},
        ("ETH/KRW", "dca"): {"action": "hold", "latest_price": 970.0, "confidence": 0.0, "target_notional": 0.0, "market_regime": {"regime": "trend_down"}},
    })
    service = make_service(
        tmp_path,
        Settings(
            symbols=["BTC/KRW", "ETH/KRW"],
            auto_trade_stop_loss_pct=1.5,
            auto_trade_partial_take_profit_pct=2.0,
            auto_trade_trailing_stop_pct=0.5,
            auto_trade_partial_sell_ratio=0.5,
            auto_trade_min_managed_position_notional=100.0,
        ),
        shadow,
        FakeAccountService(
            krw_cash=0.0,
            asset_balances={"BTC/KRW": 10.0, "ETH/KRW": 10.0},
            avg_buy_prices={"BTC/KRW": 1000.0, "ETH/KRW": 1000.0},
        ),
    )
    service._peak_price_by_symbol["BTC/KRW"] = 1030.0

    result = service.run_once()

    assert result["status"] == "submitted"
    assert result["symbol"] == "ETH/KRW"
    assert result["side"] == "sell"
    assert result["override"]["override_reason"] == "stop_loss"
    assert result["submit"]["volume"] == 10.0
