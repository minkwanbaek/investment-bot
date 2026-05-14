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
        monkeypatch.setattr(TrendFollowingStrategy, "min_entry_volume_ratio", 1.3)
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


def test_replay_backtest_tighter_entry_close_location_skips_soft_breakout_reversal(monkeypatch):
    from investment_bot.strategies.trend_following import TrendFollowingStrategy

    def make_candles() -> list[Candle]:
        closes = [
            100.0,
            100.7,
            101.4,
            102.1,
            102.8,
            103.5,
            105.0,
            106.4,
            103.8,
            102.9,
            102.4,
            103.2,
            104.2,
            105.2,
            106.2,
            107.4,
            109.0,
            111.2,
            113.2,
            114.4,
            115.2,
        ]
        candles = []
        for i, close in enumerate(closes):
            if i == 7:
                low = 103.4
                high = 107.0
                open_price = 105.0
                volume = 14.5
            elif i == 17:
                low = 110.4
                high = 111.3
                open_price = 110.5
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
                    timestamp=f"2099-01-01T05:{i:02d}:00Z",
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

    baseline = run_with_threshold(0.8)
    candidate = run_with_threshold(0.85)

    assert baseline["runs"][0]["signal"]["action"] == "buy"
    assert baseline["runs"][0]["signal"]["meta"]["entry_close_location"] == 0.833333
    assert candidate["runs"][0]["signal"]["action"] == "hold"
    assert candidate["runs"][0]["signal"]["meta"]["entry_close_location"] == 0.833333
    assert candidate["metrics"]["return_pct"] > baseline["metrics"]["return_pct"]
    assert candidate["metrics"]["max_drawdown_pct"] < baseline["metrics"]["max_drawdown_pct"]
    assert candidate["metrics"]["profit_factor"] > baseline["metrics"]["profit_factor"]


def test_replay_backtest_stronger_volume_gate_1p45_skips_weak_breakout_reversal(monkeypatch):
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
                low = 107.8
                high = 108.6
                open_price = 107.8
                volume = 14.2
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

    baseline = run_with_volume_ratio(1.4)
    candidate = run_with_volume_ratio(1.45)

    assert baseline["runs"][0]["signal"]["action"] == "hold"
    assert baseline["runs"][0]["signal"]["meta"]["entry_volume_ratio"] == 1.42
    assert baseline["runs"][0]["signal"]["meta"]["entry_close_location"] == 0.875
    assert candidate["runs"][0]["signal"]["action"] == "hold"
    assert candidate["runs"][0]["signal"]["meta"]["entry_volume_ratio"] == 1.42
    assert candidate["metrics"]["return_pct"] == baseline["metrics"]["return_pct"] == 0.0
    assert candidate["metrics"]["max_drawdown_pct"] == baseline["metrics"]["max_drawdown_pct"] == 0.0
    assert candidate["metrics"]["ending_equity"] == baseline["metrics"]["ending_equity"] == 10000000.0


def test_replay_backtest_lower_trend_gap_enters_early_continuation(monkeypatch):
    from investment_bot.strategies.trend_following import TrendFollowingStrategy

    def make_candles() -> list[Candle]:
        closes = [
            99.9,
            99.95,
            100.0,
            100.0,
            100.0,
            100.0,
            100.0,
            100.05,
            100.1,
            100.15,
            100.2,
            100.25,
            100.3,
            100.45,
            100.75,
            101.1,
            101.5,
            101.8,
            102.0,
        ]
        candles = []
        for i, close in enumerate(closes):
            volume = 14.0 if i == 13 else 10.0
            if i > 13:
                volume = 12.0
            candles.append(
                Candle(
                    symbol="BTC/KRW",
                    timeframe="5m",
                    open=close - 0.6,
                    high=close + 0.05,
                    low=close - 0.6,
                    close=close,
                    volume=volume,
                    timestamp=f"2099-01-01T04:{i:02d}:00Z",
                )
            )
        return candles

    def run_with_trend_gap(threshold: float) -> dict:
        monkeypatch.setattr(TrendFollowingStrategy, "min_trend_gap_pct", threshold)
        monkeypatch.setattr(TrendFollowingStrategy, "min_entry_volume_ratio", 1.3)
        monkeypatch.setattr(TrendFollowingStrategy, "min_entry_close_location", 0.8)
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
            window=14,
            steps=6,
        )

    baseline = run_with_trend_gap(0.0015)
    candidate = run_with_trend_gap(0.0012)

    assert baseline["runs"][0]["signal"]["action"] == "hold"
    assert baseline["runs"][0]["signal"]["meta"]["trend_gap_pct"] == 0.001456
    assert candidate["runs"][0]["signal"]["action"] == "buy"
    assert candidate["runs"][0]["signal"]["meta"]["route_exception_pass"] is True
    assert candidate["metrics"]["return_pct"] > baseline["metrics"]["return_pct"]
    assert candidate["metrics"]["profit_factor"] is not None
    assert candidate["metrics"]["max_drawdown_pct"] == 0.005


def test_replay_backtest_lower_entry_momentum_enters_smooth_continuation_earlier(monkeypatch):
    from investment_bot.strategies.trend_following import TrendFollowingStrategy

    def make_candles() -> list[Candle]:
        closes = [
            99.2,
            100.0,
            100.0,
            100.0,
            100.0,
            100.0,
            100.3,
            100.41,
            100.7,
            101.0,
            101.35,
            101.75,
            102.1,
            101.95,
            101.8,
        ]
        candles = []
        for i, close in enumerate(closes):
            volume = 15.0 if i == 7 else (16.0 if i == 8 else 10.0)
            candles.append(
                Candle(
                    symbol="BTC/KRW",
                    timeframe="5m",
                    open=close - 0.6,
                    high=close + 0.05,
                    low=close - 0.6,
                    close=close,
                    volume=volume,
                    timestamp=f"2099-01-01T05:{i:02d}:00Z",
                )
            )
        return candles

    def run_with_momentum_threshold(threshold: float) -> dict:
        monkeypatch.setattr(TrendFollowingStrategy, "min_entry_momentum_pct", threshold)
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
            steps=8,
        )

    baseline = run_with_momentum_threshold(0.0012)
    candidate = run_with_momentum_threshold(0.0010)

    assert baseline["runs"][0]["signal"]["action"] == "hold"
    assert baseline["runs"][0]["signal"]["meta"]["momentum_pct"] == 0.001097
    assert candidate["runs"][0]["signal"]["action"] == "buy"
    assert candidate["runs"][0]["signal"]["meta"]["momentum_pct"] == 0.001097
    assert candidate["metrics"]["return_pct"] > baseline["metrics"]["return_pct"]
    assert candidate["metrics"]["profit_factor"] is not None
    assert candidate["metrics"]["max_drawdown_pct"] < 0.03


def test_replay_backtest_high_volatility_half_size_reduces_reversal_loss(monkeypatch):
    from investment_bot.core.settings import get_settings

    def make_candles() -> list[Candle]:
        closes = [
            98.8,
            99.0,
            99.2,
            99.1,
            99.4,
            99.6,
            100.0,
            100.2,
            100.4,
            100.3,
            100.5,
            100.7,
            101.0,
            104.0,
            101.2,
            100.6,
            99.8,
        ]
        candles = []
        for i, close in enumerate(closes):
            if i == 13:
                low = 98.0
                high = 104.2
                open_price = 99.0
                volume = 18.0
            else:
                low = close - 3.2
                high = close + 0.25
                open_price = close - 3.0
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
                    timestamp=f"2099-01-01T05:{i:02d}:00Z",
                )
            )
        return candles

    def run_with_high_volatility_multiplier(multiplier: float) -> dict:
        settings = get_settings()
        monkeypatch.setattr(settings, "volatility_size_multipliers", {"low": 1.0, "normal": 1.0, "high": multiplier})
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
            window=14,
            steps=5,
        )

    baseline = run_with_high_volatility_multiplier(0.75)
    candidate = run_with_high_volatility_multiplier(0.5)

    assert baseline["runs"][0]["signal"]["action"] == "hold"
    assert baseline["runs"][0]["signal"]["meta"]["entry_momentum_capped"] is True
    assert baseline["runs"][0]["review"]["volatility_state"] == "high"
    assert baseline["runs"][0]["review"]["target_notional"] == 0.0
    assert candidate["runs"][0]["review"]["target_notional"] == 0.0
    assert candidate["metrics"]["ending_equity"] == baseline["metrics"]["ending_equity"] == 10000000.0
    assert candidate["metrics"]["return_pct"] == baseline["metrics"]["return_pct"] == 0.0
    assert candidate["metrics"]["max_drawdown_pct"] == baseline["metrics"]["max_drawdown_pct"] == 0.0


def test_replay_backtest_high_volatility_0p4_size_reduces_reversal_loss(monkeypatch):
    from investment_bot.core.settings import get_settings

    def make_candles() -> list[Candle]:
        closes = [
            98.8,
            99.0,
            99.2,
            99.1,
            99.4,
            99.6,
            100.0,
            100.2,
            100.4,
            100.3,
            100.5,
            100.7,
            101.0,
            104.0,
            101.2,
            100.6,
            99.8,
        ]
        candles = []
        for i, close in enumerate(closes):
            if i == 13:
                low = 98.0
                high = 104.2
                open_price = 99.0
                volume = 18.0
            else:
                low = close - 3.2
                high = close + 0.25
                open_price = close - 3.0
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
                    timestamp=f"2099-01-01T05:{i:02d}:00Z",
                )
            )
        return candles

    def run_with_high_volatility_multiplier(multiplier: float) -> dict:
        settings = get_settings()
        monkeypatch.setattr(settings, "volatility_size_multipliers", {"low": 1.0, "normal": 1.0, "high": multiplier})
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
            window=14,
            steps=5,
        )

    baseline = run_with_high_volatility_multiplier(0.5)
    candidate = run_with_high_volatility_multiplier(0.4)

    assert baseline["runs"][0]["signal"]["action"] == "hold"
    assert baseline["runs"][0]["signal"]["meta"]["entry_momentum_capped"] is True
    assert baseline["runs"][0]["review"]["volatility_state"] == "high"
    assert baseline["runs"][0]["review"]["target_notional"] == 0.0
    assert candidate["runs"][0]["review"]["target_notional"] == 0.0
    assert candidate["metrics"]["ending_equity"] == baseline["metrics"]["ending_equity"] == 10000000.0
    assert candidate["metrics"]["return_pct"] == baseline["metrics"]["return_pct"] == 0.0
    assert candidate["metrics"]["max_drawdown_pct"] == baseline["metrics"]["max_drawdown_pct"] == 0.0
    assert candidate["metrics"]["order_count"] == baseline["metrics"]["order_count"] == 0


def test_replay_backtest_high_volatility_0p35_size_reduces_reversal_loss(monkeypatch):
    from investment_bot.core.settings import get_settings

    def make_candles() -> list[Candle]:
        closes = [
            98.8,
            99.0,
            99.2,
            99.1,
            99.4,
            99.6,
            100.0,
            100.2,
            100.4,
            100.3,
            100.5,
            100.7,
            101.0,
            104.0,
            101.2,
            100.6,
            99.8,
        ]
        candles = []
        for i, close in enumerate(closes):
            if i == 13:
                low = 98.0
                high = 104.2
                open_price = 99.0
                volume = 18.0
            else:
                low = close - 3.2
                high = close + 0.25
                open_price = close - 3.0
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
                    timestamp=f"2099-01-01T05:{i:02d}:00Z",
                )
            )
        return candles

    def run_with_high_volatility_multiplier(multiplier: float) -> dict:
        settings = get_settings()
        monkeypatch.setattr(settings, "volatility_size_multipliers", {"low": 1.15, "normal": 1.0, "high": multiplier})
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
            window=14,
            steps=5,
        )

    baseline = run_with_high_volatility_multiplier(0.4)
    candidate = run_with_high_volatility_multiplier(0.35)

    assert baseline["runs"][0]["signal"]["action"] == "hold"
    assert baseline["runs"][0]["signal"]["meta"]["entry_momentum_capped"] is True
    assert baseline["runs"][0]["review"]["volatility_state"] == "high"
    assert baseline["runs"][0]["review"]["target_notional"] == 0.0
    assert candidate["runs"][0]["review"]["target_notional"] == 0.0
    assert candidate["metrics"]["ending_equity"] == baseline["metrics"]["ending_equity"] == 10000000.0
    assert candidate["metrics"]["return_pct"] == baseline["metrics"]["return_pct"] == 0.0
    assert candidate["metrics"]["max_drawdown_pct"] == baseline["metrics"]["max_drawdown_pct"] == 0.0
    assert candidate["metrics"]["order_count"] == baseline["metrics"]["order_count"] == 0


def test_replay_backtest_low_volatility_1p15_size_expands_smooth_continuation_profit(monkeypatch):
    from investment_bot.core.settings import get_settings

    def make_candles() -> list[Candle]:
        closes = [
            100.0,
            100.2,
            100.4,
            100.6,
            100.8,
            101.0,
            101.2,
            101.4,
            101.6,
            101.8,
            102.0,
            102.3,
            102.7,
            103.2,
            104.6,
            105.4,
            104.9,
        ]
        candles = []
        for i, close in enumerate(closes):
            volume = 16.0 if i == 13 else 10.0
            candles.append(
                Candle(
                    symbol="BTC/KRW",
                    timeframe="5m",
                    open=close - 0.2,
                    high=close + 0.02,
                    low=close - 0.35,
                    close=close,
                    volume=volume,
                    timestamp=f"2099-01-01T06:{i:02d}:00Z",
                )
            )
        return candles

    def run_with_low_volatility_multiplier(multiplier: float) -> dict:
        settings = get_settings()
        monkeypatch.setattr(settings, "volatility_size_multipliers", {"low": multiplier, "normal": 1.0, "high": 0.4})
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
            window=14,
            steps=4,
        )

    baseline = run_with_low_volatility_multiplier(1.0)
    candidate = run_with_low_volatility_multiplier(1.15)

    assert baseline["runs"][0]["signal"]["action"] == "buy"
    assert baseline["runs"][0]["review"]["volatility_state"] == "low"
    assert baseline["runs"][0]["review"]["target_notional"] == 500000.0
    assert candidate["runs"][0]["review"]["target_notional"] == 575000.0
    assert candidate["metrics"]["ending_equity"] > baseline["metrics"]["ending_equity"]
    assert candidate["metrics"]["return_pct"] > baseline["metrics"]["return_pct"]
    assert candidate["metrics"]["profit_factor"] == baseline["metrics"]["profit_factor"]
    assert candidate["metrics"]["max_drawdown_pct"] < 0.05
    assert candidate["metrics"]["order_count"] == baseline["metrics"]["order_count"]


def test_trading_cycle_applies_strategy_stop_loss_exit():
    candles = [
        Candle(symbol="BTC/KRW", timeframe="1h", open=close, high=close, low=close, close=close, volume=10, timestamp=str(i))
        for i, close in enumerate([100, 100.2, 100.4, 100.6, 100.8, 100.6, 100.2, 98.4], start=1)
    ]
    paper_broker = PaperBroker(starting_cash=1000, min_order_notional=0.0)
    paper_broker.positions["BTC/KRW"] = {
        "quantity": 1.0,
        "average_price": 100.0,
        "realized_pnl": 0.0,
        "opened_at": None,
        "stop_price": None,
        "tp1_price": None,
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
    assert result["signal"]["meta"]["exit_reason"] == "stop_loss"
    assert result["signal"]["meta"]["exit_source"] == "strategy"
    assert result["signal"]["meta"]["exit_priority"] == 100
    assert result["review"]["size_scale"] == 1.0


def test_trading_cycle_broker_exit_takes_precedence_over_strategy_exit():
    candles = [
        Candle(symbol="BTC/KRW", timeframe="1h", open=close, high=close, low=close, close=close, volume=10, timestamp=str(i))
        for i, close in enumerate([100, 100.2, 100.4, 100.6, 100.8, 100.6, 100.2, 98.4], start=1)
    ]
    paper_broker = PaperBroker(starting_cash=1000, min_order_notional=0.0)
    paper_broker.positions["BTC/KRW"] = {
        "quantity": 1.0,
        "average_price": 100.0,
        "realized_pnl": 0.0,
        "opened_at": None,
        "stop_price": 99.0,
        "tp1_price": None,
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
    assert result["signal"]["meta"]["exit_reason"] == "atr_stop"
    assert result["signal"]["meta"]["exit_source"] == "broker"
    assert result["signal"]["meta"]["exit_priority"] == 240
    assert result["signal"]["meta"]["exit_priority_label"] == "hard_stop"
    assert result["review"]["size_scale"] == 1.0


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
    assert result["signal"]["meta"]["exit_source"] == "broker"
    assert result["signal"]["meta"]["exit_priority"] == 220
    assert result["signal"]["meta"]["exit_priority_label"] == "profit_take"
    assert result["review"]["size_scale"] == 0.5


def test_trading_cycle_applies_mean_reversion_managed_rebound_exit():
    candles = [
        Candle(symbol="ETH/KRW", timeframe="1h", open=1, high=1, low=1, close=c, volume=1, timestamp=str(i))
        for i, c in enumerate([98, 99, 99, 100, 100, 100, 100, 101.3], start=1)
    ]
    paper_broker = PaperBroker(starting_cash=1000, min_order_notional=0.0)
    paper_broker.positions["ETH/KRW"] = {
        "quantity": 2.0,
        "average_price": 100.0,
        "realized_pnl": 0.0,
        "opened_at": None,
        "stop_price": None,
        "tp1_price": None,
        "tp1_done": False,
        "trailing_active": False,
        "trailing_stop_price": None,
    }
    trading_cycle_service = TradingCycleService(
        risk_controller=RiskController(max_confidence_position_scale=0.01),
        paper_broker=paper_broker,
    )

    result = trading_cycle_service.run(strategy_name="mean_reversion", candles=candles)

    assert result["signal"]["action"] == "sell"
    assert result["signal"]["meta"]["force_exit"] is True
    assert result["signal"]["meta"]["exit_reason"] == "mean_reversion_managed_rebound_exit"
    assert result["review"]["size_scale"] == 2.0


def test_trading_cycle_applies_dca_managed_rebound_exit():
    candles = [
        Candle(symbol="BTC/KRW", timeframe="1h", open=1, high=1, low=1, close=c, volume=1, timestamp=str(i))
        for i, c in enumerate([98, 99, 99, 100, 100, 100, 100, 101.3], start=1)
    ]
    paper_broker = PaperBroker(starting_cash=1000, min_order_notional=0.0)
    paper_broker.positions["BTC/KRW"] = {
        "quantity": 2.0,
        "average_price": 100.0,
        "realized_pnl": 0.0,
        "opened_at": None,
        "stop_price": None,
        "tp1_price": None,
        "tp1_done": False,
        "trailing_active": False,
        "trailing_stop_price": None,
    }
    trading_cycle_service = TradingCycleService(
        risk_controller=RiskController(max_confidence_position_scale=0.01),
        paper_broker=paper_broker,
    )

    result = trading_cycle_service.run(strategy_name="dca", candles=candles)

    assert result["signal"]["action"] == "sell"
    assert result["signal"]["meta"]["force_exit"] is True
    assert result["signal"]["meta"]["exit_reason"] == "value_dca_rebound_exit"
    assert result["review"]["size_scale"] == 2.0


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


def test_replay_backtest_higher_timeout_progress_exits_stale_winner_before_reversal(monkeypatch):
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
            timestamp=timestamp,
        )
        for timestamp, close in [
            ("2099-01-01T01:30:00Z", 100.4),
            ("2099-01-01T01:35:00Z", 100.1),
            ("2099-01-01T01:40:00Z", 99.6),
            ("2099-01-01T01:45:00Z", 99.0),
        ]
    ]

    def run_with_min_progress(min_progress_pct: float) -> dict:
        settings = get_settings()
        monkeypatch.setattr(settings, "max_holding_minutes", 90)
        monkeypatch.setattr(settings, "min_progress_pct", min_progress_pct)
        market_data_service = MarketDataService(registry=build_default_market_data_registry())
        paper_broker = PaperBroker(
            starting_cash=10_000_000,
            min_order_notional=5000,
            max_symbol_exposure_pct=20,
        )
        paper_broker.cash_balance = 9_900_000
        paper_broker.positions["BTC/KRW"] = {
            "quantity": 1000.0,
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

    baseline = run_with_min_progress(0.003)
    candidate = run_with_min_progress(0.005)

    assert baseline["runs"][0]["signal"]["action"] == "hold"
    assert candidate["runs"][0]["signal"]["meta"]["exit_reason"] == "timeout"
    assert candidate["metrics"]["ending_equity"] > baseline["metrics"]["ending_equity"]
    assert candidate["metrics"]["return_pct"] > baseline["metrics"]["return_pct"]
    assert candidate["metrics"]["max_drawdown_pct"] < baseline["metrics"]["max_drawdown_pct"]
    assert candidate["metrics"]["total_realized_pnl"] > baseline["metrics"]["total_realized_pnl"]


def test_replay_backtest_stricter_timeout_progress_exits_marginal_winner_before_reversal(monkeypatch):
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
            timestamp=timestamp,
        )
        for timestamp, close in [
            ("2099-01-01T01:30:00Z", 100.55),
            ("2099-01-01T01:35:00Z", 100.05),
            ("2099-01-01T01:40:00Z", 99.30),
            ("2099-01-01T01:45:00Z", 98.90),
        ]
    ]

    def run_with_min_progress(min_progress_pct: float) -> dict:
        settings = get_settings()
        monkeypatch.setattr(settings, "max_holding_minutes", 90)
        monkeypatch.setattr(settings, "min_progress_pct", min_progress_pct)
        market_data_service = MarketDataService(registry=build_default_market_data_registry())
        paper_broker = PaperBroker(
            starting_cash=10_000_000,
            min_order_notional=5000,
            max_symbol_exposure_pct=20,
        )
        paper_broker.cash_balance = 9_900_000
        paper_broker.positions["BTC/KRW"] = {
            "quantity": 1000.0,
            "average_price": 100.0,
            "realized_pnl": 0.0,
            "opened_at": "2099-01-01T00:00:00Z",
            "stop_price": 98.0,
            "tp1_price": 101.2,
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

    baseline = run_with_min_progress(0.005)
    candidate = run_with_min_progress(0.006)

    assert baseline["runs"][0]["signal"]["action"] == "hold"
    assert candidate["runs"][0]["signal"]["meta"]["exit_reason"] == "timeout"
    assert candidate["metrics"]["ending_equity"] > baseline["metrics"]["ending_equity"]
    assert candidate["metrics"]["return_pct"] > baseline["metrics"]["return_pct"]
    assert candidate["metrics"]["max_drawdown_pct"] < baseline["metrics"]["max_drawdown_pct"]
    assert candidate["metrics"]["total_realized_pnl"] > baseline["metrics"]["total_realized_pnl"]


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


def test_replay_backtest_lower_tp1_ratio_captures_shallow_winner(monkeypatch):
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
            (0, 101.3),
            (5, 100.4),
            (10, 100.1),
        ]
    ]

    def run_with_tp1_ratio(tp1_ratio: float) -> dict:
        settings = get_settings()
        monkeypatch.setattr(settings, "tp1_ratio", tp1_ratio)
        monkeypatch.setattr(settings, "tp1_size_pct", 0.25)
        monkeypatch.setattr(settings, "trailing_activation_ratio", 0.02)
        monkeypatch.setattr(settings, "trailing_distance_ratio", 0.006)
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
            "tp1_price": round(100.0 * (1 + tp1_ratio), 4),
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

    baseline = run_with_tp1_ratio(0.015)
    candidate = run_with_tp1_ratio(0.012)

    assert baseline["runs"][0]["signal"]["action"] == "hold"
    assert candidate["runs"][0]["signal"]["meta"]["exit_reason"] == "partial_take_profit"
    assert candidate["metrics"]["return_pct"] > baseline["metrics"]["return_pct"]
    assert candidate["metrics"]["total_realized_pnl"] > baseline["metrics"]["total_realized_pnl"]
    assert candidate["metrics"]["max_drawdown_pct"] <= baseline["metrics"]["max_drawdown_pct"]


def test_replay_backtest_lower_trailing_activation_captures_pre_tp1_fade(monkeypatch):
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
            (0, 101.9),
            (5, 101.2),
            (10, 100.3),
        ]
    ]

    def run_with_trailing_activation(trailing_activation_ratio: float) -> dict:
        settings = get_settings()
        monkeypatch.setattr(settings, "tp1_ratio", 0.012)
        monkeypatch.setattr(settings, "tp1_size_pct", 0.25)
        monkeypatch.setattr(settings, "trailing_activation_ratio", trailing_activation_ratio)
        monkeypatch.setattr(settings, "trailing_distance_ratio", 0.006)
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

    baseline = run_with_trailing_activation(0.02)
    candidate = run_with_trailing_activation(0.018)

    assert baseline["runs"][1]["signal"]["action"] == "hold"
    assert candidate["runs"][1]["signal"]["meta"]["exit_reason"] == "trailing_stop"
    assert candidate["metrics"]["ending_equity"] > baseline["metrics"]["ending_equity"]
    assert candidate["metrics"]["return_pct"] > baseline["metrics"]["return_pct"]
    assert candidate["metrics"]["max_drawdown_pct"] < baseline["metrics"]["max_drawdown_pct"]
    assert candidate["metrics"]["total_realized_pnl"] > baseline["metrics"]["total_realized_pnl"]


def test_replay_backtest_smaller_tp1_size_keeps_more_runner_exposure(monkeypatch):
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
            timestamp=f"2099-01-01T03:{minute:02d}:00Z",
        )
        for minute, close in [
            (0, 101.6),
            (5, 102.4),
            (10, 103.2),
            (15, 104.0),
            (20, 103.3),
        ]
    ]

    def run_with_tp1_size(tp1_size_pct: float) -> dict:
        settings = get_settings()
        monkeypatch.setattr(settings, "tp1_ratio", 0.015)
        monkeypatch.setattr(settings, "tp1_size_pct", tp1_size_pct)
        monkeypatch.setattr(settings, "trailing_activation_ratio", 0.02)
        monkeypatch.setattr(settings, "trailing_distance_ratio", 0.006)
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
            "opened_at": "2099-01-01T02:00:00Z",
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

    baseline = run_with_tp1_size(0.33)
    candidate = run_with_tp1_size(0.25)

    assert baseline["runs"][0]["review"]["size_scale"] == 330.0
    assert candidate["runs"][0]["review"]["size_scale"] == 250.0
    assert baseline["runs"][4]["signal"]["meta"]["exit_reason"] == "trailing_stop"
    assert candidate["runs"][4]["signal"]["meta"]["exit_reason"] == "trailing_stop"
    assert candidate["metrics"]["return_pct"] > baseline["metrics"]["return_pct"]
    assert candidate["metrics"]["profit_factor"] > 100
    assert candidate["metrics"]["profit_factor"] < baseline["metrics"]["profit_factor"]
    assert candidate["metrics"]["max_drawdown_pct"] > baseline["metrics"]["max_drawdown_pct"]
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
