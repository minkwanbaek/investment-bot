from investment_bot.market_data.registry import build_default_market_data_registry
from investment_bot.models.market import Candle
from investment_bot.risk.controller import RiskController
from investment_bot.services.backtest_service import BacktestService
from investment_bot.services.market_data_service import MarketDataService
from investment_bot.services.paper_broker import PaperBroker
from investment_bot.services.trading_cycle import TradingCycleService


def test_replay_backtest_runs_multiple_steps_and_returns_summary():
    market_data_service = MarketDataService(registry=build_default_market_data_registry())
    paper_broker = PaperBroker(starting_cash=1000)
    trading_cycle_service = TradingCycleService(
        risk_controller=RiskController(max_confidence_position_scale=0.01),
        paper_broker=paper_broker,
    )
    backtest_service = BacktestService(
        market_data_service=market_data_service,
        paper_broker=paper_broker,
        trading_cycle_service=trading_cycle_service,
    )

    candles = [
        Candle(symbol="BTC/KRW", timeframe="1h", open=1, high=1, low=1, close=close, volume=1, timestamp=str(i))
        for i, close in enumerate([100, 101, 102, 103, 104, 105, 106], start=1)
    ]
    market_data_service.load_replay(symbol="BTC/KRW", timeframe="1h", candles=candles)

    result = backtest_service.run_replay(
        strategy_name="trend_following",
        symbol="BTC/KRW",
        timeframe="1h",
        window=5,
        steps=2,
    )

    assert result["steps"] == 2
    assert len(result["runs"]) == 2
    assert result["runs"][0]["timestamp"] == "5"
    assert result["runs"][1]["timestamp"] == "6"
    assert result["final_portfolio"]["order_count"] >= 1
