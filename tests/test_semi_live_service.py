from investment_bot.market_data.registry import build_default_market_data_registry
from investment_bot.models.market import Candle
from investment_bot.risk.controller import RiskController
from investment_bot.services.market_data_service import MarketDataService
from investment_bot.services.paper_broker import PaperBroker
from investment_bot.services.run_history_service import RunHistoryService
from investment_bot.services.run_history_store import RunHistoryStore
from investment_bot.services.semi_live_service import SemiLiveService
from investment_bot.services.trading_cycle import TradingCycleService


class FakeLiveMarketDataService(MarketDataService):
    def get_recent_candles(self, adapter_name: str, symbol: str, timeframe: str, limit: int):
        return [
            Candle(symbol=symbol, timeframe=timeframe, open=1, high=1, low=1, close=close, volume=1, timestamp=str(i))
            for i, close in enumerate([100, 101, 102, 103, 104], start=1)
        ][-limit:]


def test_semi_live_service_runs_once_and_records_history(tmp_path):
    market_data_service = FakeLiveMarketDataService(registry=build_default_market_data_registry())
    paper_broker = PaperBroker(starting_cash=1000, trading_fee_pct=0.0, slippage_pct=0.0, min_order_notional=0.0)
    trading_cycle_service = TradingCycleService(
        risk_controller=RiskController(max_confidence_position_scale=0.01),
        paper_broker=paper_broker,
    )
    run_history_service = RunHistoryService(store=RunHistoryStore(str(tmp_path / "run_history.json")))

    service = SemiLiveService(
        market_data_service=market_data_service,
        trading_cycle_service=trading_cycle_service,
        run_history_service=run_history_service,
    )

    result = service.run_once(
        strategy_name="trend_following",
        symbol="BTC/KRW",
        timeframe="1h",
        limit=5,
    )

    assert result["adapter"] == "live"
    assert result["signal"]["action"] == "buy"
    assert result["portfolio"]["order_count"] == 1
    assert len(run_history_service.list_recent(limit=10)) == 1
