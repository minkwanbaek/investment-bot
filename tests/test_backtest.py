from investment_bot.market_data.registry import build_default_market_data_registry
from investment_bot.models.market import Candle
from investment_bot.models.signal import TradeSignal
from investment_bot.risk.controller import RiskController
from investment_bot.services.backtest_service import BacktestService
from investment_bot.services.market_data_service import MarketDataService
from investment_bot.services.metrics_service import MetricsService
from investment_bot.services.paper_broker import PaperBroker
from investment_bot.services.trading_cycle import TradingCycleService


def test_replay_backtest_runs_multiple_steps_and_returns_summary():
    market_data_service = MarketDataService(registry=build_default_market_data_registry())
    paper_broker = PaperBroker(starting_cash=1000, min_order_notional=0.0)
    trading_cycle_service = TradingCycleService(
        risk_controller=RiskController(max_confidence_position_scale=0.01),
        paper_broker=paper_broker,
    )
    backtest_service = BacktestService(
        market_data_service=market_data_service,
        paper_broker=paper_broker,
        trading_cycle_service=trading_cycle_service,
        metrics_service=MetricsService(),
    )

    closes = [100, 101, 102, 103, 104, 105, 106, 108, 110]
    volumes = [1, 1, 1, 1, 1, 1, 1, 2, 2]
    candles = [
        Candle(symbol="BTC/KRW", timeframe="1h", open=close - 1, high=close, low=close - 2, close=close, volume=volume, timestamp=str(i))
        for i, (close, volume) in enumerate(zip(closes, volumes), start=1)
    ]
    market_data_service.load_replay(symbol="BTC/KRW", timeframe="1h", candles=candles)

    result = backtest_service.run_replay(
        strategy_name="trend_following",
        symbol="BTC/KRW",
        timeframe="1h",
        window=8,
        steps=2,
    )

    assert result["steps"] == 2
    assert len(result["runs"]) == 2
    assert result["runs"][0]["timestamp"] == "8"
    assert result["runs"][1]["timestamp"] == "9"
    assert result["metrics"]["total_steps"] == 2
    assert result["metrics"]["equity_curve"][0] == 1000
    assert "win_rate_pct" in result["metrics"]
    assert result["metrics"]["order_count"] >= 1
    assert result["final_portfolio"]["order_count"] >= 1


def test_replay_backtest_close_location_gate_skips_wick_fakeout(monkeypatch):
    from investment_bot.strategies.trend_following import TrendFollowingStrategy

    def make_candles() -> list[Candle]:
        closes = [
            100.0,
            101.0,
            102.0,
            103.0,
            104.0,
            105.0,
            107.0,
            108.7,
            106.0,
            105.5,
            104.5,
            105.0,
            106.0,
            107.0,
            108.0,
            109.0,
            111.0,
            113.0,
            115.0,
            116.0,
            117.0,
        ]
        candles = []
        for i, close in enumerate(closes):
            if i == 7:
                low = 100.0
                high = 111.2987
                open_price = 107.0
            elif i == 17:
                low = 111.0
                high = 113.2
                open_price = 111.0
            else:
                low = close - 0.2
                high = close + 0.2
                open_price = close - 0.1
            volume = 10.0 if i < 7 else (13.0 if i == 7 else (10.0 if i < 17 else 14.0))
            candles.append(
                Candle(
                    symbol="BTC/KRW",
                    timeframe="5m",
                    open=open_price,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                    timestamp=f"2099-01-01T00:{i:02d}:00Z",
                )
            )
        return candles

    def run_with_threshold(threshold: float) -> dict:
        monkeypatch.setattr(TrendFollowingStrategy, "min_entry_close_location", threshold)
        market_data_service = MarketDataService(registry=build_default_market_data_registry())
        paper_broker = PaperBroker(
            starting_cash=10_000_000,
            min_order_notional=5000,
            max_symbol_exposure_pct=20,
        )
        trading_cycle_service = TradingCycleService(
            risk_controller=RiskController(min_order_notional=5000, base_entry_notional=10000),
            paper_broker=paper_broker,
        )
        backtest_service = BacktestService(
            market_data_service=market_data_service,
            paper_broker=paper_broker,
            trading_cycle_service=trading_cycle_service,
            metrics_service=MetricsService(),
        )
        market_data_service.load_replay(symbol="BTC/KRW", timeframe="5m", candles=make_candles())
        return backtest_service.run_replay(
            strategy_name="trend_following",
            symbol="BTC/KRW",
            timeframe="5m",
            window=8,
            steps=14,
        )

    baseline = run_with_threshold(0.75)
    candidate = run_with_threshold(0.8)

    assert baseline["runs"][0]["signal"]["action"] == "buy"
    assert baseline["runs"][0]["signal"]["meta"]["entry_close_location"] == 0.77
    assert candidate["runs"][0]["signal"]["action"] == "hold"
    assert candidate["runs"][0]["signal"]["meta"]["entry_close_location"] == 0.77
    assert candidate["metrics"]["return_pct"] > baseline["metrics"]["return_pct"]
    assert candidate["metrics"]["max_drawdown_pct"] < baseline["metrics"]["max_drawdown_pct"]
    assert candidate["metrics"]["profit_factor"] > baseline["metrics"]["profit_factor"]


def test_replay_backtest_stronger_volume_gate_skips_weak_breakout_reversal(monkeypatch):
    from investment_bot.strategies.trend_following import TrendFollowingStrategy

    def make_candles() -> list[Candle]:
        closes = [
            100.0,
            101.0,
            102.0,
            103.0,
            104.0,
            105.0,
            107.0,
            108.5,
            105.8,
            104.8,
            104.0,
            105.0,
            106.0,
            107.0,
            108.0,
            109.0,
            111.0,
            113.0,
            115.0,
            116.0,
            117.0,
        ]
        candles = []
        for i, close in enumerate(closes):
            if i == 7:
                low = 107.5
                high = 108.7
                open_price = 107.8
                volume = 12.5
            elif i == 17:
                low = 112.1
                high = 113.2
                open_price = 112.2
                volume = 16.0
            else:
                low = close - 0.2
                high = close + 0.2
                open_price = close - 0.1
                volume = 10.0
            candles.append(
                Candle(
                    symbol="BTC/KRW",
                    timeframe="5m",
                    open=open_price,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                    timestamp=f"2099-01-01T03:{i:02d}:00Z",
                )
            )
        return candles

    def run_with_volume_ratio(threshold: float) -> dict:
        monkeypatch.setattr(TrendFollowingStrategy, "min_entry_volume_ratio", threshold)
        market_data_service = MarketDataService(registry=build_default_market_data_registry())
        paper_broker = PaperBroker(
            starting_cash=10_000_000,
            min_order_notional=5000,
            max_symbol_exposure_pct=20,
        )
        trading_cycle_service = TradingCycleService(
            risk_controller=RiskController(min_order_notional=5000, base_entry_notional=10000),
            paper_broker=paper_broker,
        )
        backtest_service = BacktestService(
            market_data_service=market_data_service,
            paper_broker=paper_broker,
            trading_cycle_service=trading_cycle_service,
            metrics_service=MetricsService(),
        )
        market_data_service.load_replay(symbol="BTC/KRW", timeframe="5m", candles=make_candles())
        return backtest_service.run_replay(
            strategy_name="trend_following",
            symbol="BTC/KRW",
            timeframe="5m",
            window=8,
            steps=14,
        )

    baseline = run_with_volume_ratio(1.2)
    candidate = run_with_volume_ratio(1.3)

    assert baseline["runs"][0]["signal"]["action"] == "buy"
    assert baseline["runs"][0]["signal"]["meta"]["entry_volume_ratio"] == 1.25
    assert candidate["runs"][0]["signal"]["action"] == "hold"
    assert candidate["runs"][0]["signal"]["meta"]["entry_volume_ratio"] == 1.25
    assert candidate["metrics"]["return_pct"] > baseline["metrics"]["return_pct"]
    assert candidate["metrics"]["max_drawdown_pct"] < baseline["metrics"]["max_drawdown_pct"]
    assert candidate["metrics"]["profit_factor"] > baseline["metrics"]["profit_factor"]


def test_trading_cycle_applies_broker_partial_take_profit_exit():
    candles = [
        Candle(symbol="BTC/KRW", timeframe="1h", open=100, high=105, low=99, close=close, volume=1, timestamp=str(i))
        for i, close in enumerate([100, 101, 102, 103, 104, 104, 104, 104], start=1)
    ]
    paper_broker = PaperBroker(starting_cash=1000, min_order_notional=0.0)
    paper_broker.positions["BTC/KRW"] = {
        "quantity": 1.0,
        "average_price": 100.0,
        "realized_pnl": 0.0,
        "opened_at": None,
        "stop_price": 98.0,
        "tp1_price": 103.0,
        "tp1_done": False,
        "trailing_active": False,
        "trailing_stop_price": None,
    }
    trading_cycle_service = TradingCycleService(
        risk_controller=RiskController(max_confidence_position_scale=0.01),
        paper_broker=paper_broker,
    )

    result = trading_cycle_service.run(strategy_name="trend_following", candles=candles)

    assert result["signal"]["action"] == "sell"
    assert result["signal"]["meta"]["force_exit"] is True
    assert result["signal"]["meta"]["exit_reason"] == "partial_take_profit"
    assert result["review"]["size_scale"] == 0.5


def test_trading_cycle_blocks_low_volatility_sideways_breakout_exception():
    candles = [
        Candle(symbol="BTC/KRW", timeframe="5m", open=close, high=close, low=close, close=close, volume=1, timestamp=str(i))
        for i, close in enumerate([100, 100, 100, 100, 100, 100.2, 100.25, 100.38], start=1)
    ]
    trading_cycle_service = TradingCycleService(
        risk_controller=RiskController(min_order_notional=5000, base_entry_notional=10000),
        paper_broker=PaperBroker(starting_cash=10_000_000, min_order_notional=5000),
    )

    result = trading_cycle_service.run(strategy_name="trend_following", candles=candles)

    assert result["market_regime"] == "sideways"
    assert result["volatility_state"] == "low"
    assert result["signal"]["action"] == "hold"
    assert result["signal"]["meta"].get("route_exception_pass") is None
    assert result["review"]["approved"] is False


def test_trading_cycle_uses_candle_time_for_broker_timeout_exit():
    candles = [
        Candle(
            symbol="BTC/KRW",
            timeframe="5m",
            open=100,
            high=101,
            low=99,
            close=100.2,
            volume=1,
            timestamp=timestamp,
        )
        for timestamp in [
            "2099-01-01T01:00:00Z",
            "2099-01-01T01:05:00Z",
            "2099-01-01T01:10:00Z",
            "2099-01-01T01:15:00Z",
            "2099-01-01T01:20:00Z",
            "2099-01-01T01:25:00Z",
            "2099-01-01T01:30:00Z",
            "2099-01-01T01:35:00Z",
        ]
    ]
    paper_broker = PaperBroker(starting_cash=1000, min_order_notional=0.0)
    paper_broker.positions["BTC/KRW"] = {
        "quantity": 1.0,
        "average_price": 100.0,
        "realized_pnl": 0.0,
        "opened_at": "2099-01-01T00:00:00Z",
        "stop_price": 98.0,
        "tp1_price": 103.0,
        "tp1_done": False,
        "trailing_active": False,
        "trailing_stop_price": None,
    }
    trading_cycle_service = TradingCycleService(
        risk_controller=RiskController(max_confidence_position_scale=0.01),
        paper_broker=paper_broker,
    )

    result = trading_cycle_service.run(strategy_name="trend_following", candles=candles)

    assert result["signal"]["action"] == "sell"
    assert result["signal"]["meta"]["force_exit"] is True
    assert result["signal"]["meta"]["exit_reason"] == "timeout"


def test_replay_backtest_longer_timeout_holds_slow_breakout_continuation(monkeypatch):
    from investment_bot.core.settings import get_settings

    candles = [
        Candle(
            symbol="BTC/KRW",
            timeframe="5m",
            open=close - 0.1,
            high=close + 0.2,
            low=close - 0.2,
            close=close,
            volume=10.0,
            timestamp=f"2099-01-01T01:{minute:02d}:00Z",
        )
        for minute, close in [
            (0, 100.1),
            (5, 100.2),
            (10, 100.25),
            (15, 100.3),
            (20, 100.5),
            (25, 101.0),
            (30, 102.0),
        ]
    ]

    def run_with_timeout(max_holding_minutes: int) -> dict:
        settings = get_settings()
        monkeypatch.setattr(settings, "max_holding_minutes", max_holding_minutes)
        market_data_service = MarketDataService(registry=build_default_market_data_registry())
        paper_broker = PaperBroker(
            starting_cash=10_000_000,
            min_order_notional=5000,
            max_symbol_exposure_pct=20,
        )
        paper_broker.positions["BTC/KRW"] = {
            "quantity": 100.0,
            "average_price": 100.0,
            "realized_pnl": 0.0,
            "opened_at": "2099-01-01T00:00:00Z",
            "stop_price": 98.0,
            "tp1_price": 103.0,
            "tp1_done": False,
            "trailing_active": False,
            "trailing_stop_price": None,
        }
        trading_cycle_service = TradingCycleService(
            risk_controller=RiskController(min_order_notional=5000, base_entry_notional=10000),
            paper_broker=paper_broker,
        )
        backtest_service = BacktestService(
            market_data_service=market_data_service,
            paper_broker=paper_broker,
            trading_cycle_service=trading_cycle_service,
            metrics_service=MetricsService(),
        )
        market_data_service.load_replay(symbol="BTC/KRW", timeframe="5m", candles=candles)
        return backtest_service.run_replay(
            strategy_name="trend_following",
            symbol="BTC/KRW",
            timeframe="5m",
            window=1,
            steps=len(candles),
        )

    baseline = run_with_timeout(60)
    candidate = run_with_timeout(90)

    assert baseline["runs"][0]["signal"]["meta"]["exit_reason"] == "timeout"
    assert candidate["runs"][0]["signal"]["action"] != "sell"
    assert candidate["metrics"]["ending_equity"] > baseline["metrics"]["ending_equity"]
    assert candidate["metrics"]["return_pct"] > baseline["metrics"]["return_pct"]
    assert candidate["metrics"]["max_drawdown_pct"] <= baseline["metrics"]["max_drawdown_pct"]


def test_replay_backtest_tighter_trailing_stop_captures_runner_profit(monkeypatch):
    from investment_bot.core.settings import get_settings

    candles = [
        Candle(
            symbol="BTC/KRW",
            timeframe="5m",
            open=close - 0.1,
            high=close + 0.2,
            low=close - 0.2,
            close=close,
            volume=10.0,
            timestamp=f"2099-01-01T02:{minute:02d}:00Z",
        )
        for minute, close in [
            (0, 101.6),
            (5, 102.4),
            (10, 103.2),
            (15, 104.0),
            (20, 103.3),
            (25, 102.7),
        ]
    ]

    def run_with_trailing_distance(trailing_distance_ratio: float) -> dict:
        settings = get_settings()
        monkeypatch.setattr(settings, "tp1_ratio", 0.015)
        monkeypatch.setattr(settings, "tp1_size_pct", 0.33)
        monkeypatch.setattr(settings, "trailing_activation_ratio", 0.02)
        monkeypatch.setattr(settings, "trailing_distance_ratio", trailing_distance_ratio)
        market_data_service = MarketDataService(registry=build_default_market_data_registry())
        paper_broker = PaperBroker(
            starting_cash=10_000_000,
            min_order_notional=5000,
            max_symbol_exposure_pct=20,
        )
        paper_broker.positions["BTC/KRW"] = {
            "quantity": 1000.0,
            "average_price": 100.0,
            "realized_pnl": 0.0,
            "opened_at": "2099-01-01T01:00:00Z",
            "stop_price": 98.0,
            "tp1_price": 101.5,
            "tp1_done": False,
            "trailing_active": False,
            "trailing_stop_price": None,
        }
        trading_cycle_service = TradingCycleService(
            risk_controller=RiskController(min_order_notional=5000, base_entry_notional=10000),
            paper_broker=paper_broker,
        )
        backtest_service = BacktestService(
            market_data_service=market_data_service,
            paper_broker=paper_broker,
            trading_cycle_service=trading_cycle_service,
            metrics_service=MetricsService(),
        )
        market_data_service.load_replay(symbol="BTC/KRW", timeframe="5m", candles=candles)
        return backtest_service.run_replay(
            strategy_name="trend_following",
            symbol="BTC/KRW",
            timeframe="5m",
            window=1,
            steps=len(candles),
        )

    baseline = run_with_trailing_distance(0.008)
    candidate = run_with_trailing_distance(0.006)

    assert baseline["runs"][4]["signal"]["action"] == "hold"
    assert candidate["runs"][4]["signal"]["meta"]["exit_reason"] == "trailing_stop"
    assert candidate["metrics"]["return_pct"] > baseline["metrics"]["return_pct"]
    assert candidate["metrics"]["max_drawdown_pct"] < baseline["metrics"]["max_drawdown_pct"]
    assert candidate["metrics"]["profit_factor"] > baseline["metrics"]["profit_factor"]
    assert candidate["metrics"]["order_count"] == baseline["metrics"]["order_count"]


def test_trading_cycle_sells_full_position_on_strategy_sell_when_cash_sizing_is_tiny(monkeypatch):
    class SellStrategy:
        def generate_signal(self, candles, broker=None):
            return TradeSignal(
                strategy_name="cash_tiny_sell",
                symbol="BTC/KRW",
                action="sell",
                confidence=0.9,
                reason="strategy sell",
            )

    import investment_bot.services.trading_cycle as trading_cycle

    monkeypatch.setitem(trading_cycle.REGISTERED_STRATEGIES, "cash_tiny_sell", SellStrategy)
    monkeypatch.setattr(trading_cycle, "list_enabled_strategies", lambda: ["cash_tiny_sell"])
    candles = [
        Candle(symbol="BTC/KRW", timeframe="5m", open=1000, high=1010, low=990, close=1000, volume=1, timestamp=str(i))
        for i in range(8)
    ]
    paper_broker = PaperBroker(starting_cash=0, min_order_notional=5000)
    paper_broker.positions["BTC/KRW"] = {
        "quantity": 10.0,
        "average_price": 1000.0,
        "realized_pnl": 0.0,
        "opened_at": None,
        "stop_price": None,
        "tp1_price": None,
        "tp1_done": False,
        "trailing_active": False,
        "trailing_stop_price": None,
    }
    paper_broker.losing_streak = 4
    trading_cycle_service = TradingCycleService(
        risk_controller=RiskController(max_confidence_position_scale=0.075, min_order_notional=5000),
        paper_broker=paper_broker,
    )

    result = trading_cycle_service.run(strategy_name="cash_tiny_sell", candles=candles)

    assert result["broker_result"]["status"] == "recorded"
    assert result["review"]["size_scale"] == 10.0
    assert result["review"]["target_notional"] == 10000.0
