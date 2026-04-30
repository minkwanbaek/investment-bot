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
            "2099-01-01T00:30:00Z",
            "2099-01-01T00:35:00Z",
            "2099-01-01T00:40:00Z",
            "2099-01-01T00:45:00Z",
            "2099-01-01T00:50:00Z",
            "2099-01-01T00:55:00Z",
            "2099-01-01T01:00:00Z",
            "2099-01-01T01:05:00Z",
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
