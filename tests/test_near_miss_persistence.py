from investment_bot.models.market import Candle
from investment_bot.risk.controller import RiskController
from investment_bot.services.paper_broker import PaperBroker
from investment_bot.services.run_history_service import RunHistoryService
from investment_bot.services.run_history_store import RunHistoryStore
from investment_bot.services.trading_cycle import TradingCycleService


def _build_threshold_near_miss_candles(symbol: str = "BTC/KRW", timeframe: str = "1h"):
    closes = [100, 100, 100, 100, 100, 100.15, 100.18, 100.21]
    return [
        Candle(symbol=symbol, timeframe=timeframe, open=1, high=1, low=1, close=close, volume=1, timestamp=str(i))
        for i, close in enumerate(closes, start=1)
    ]


def test_trading_cycle_marks_near_miss_in_signal_meta():
    service = TradingCycleService(
        risk_controller=RiskController(max_confidence_position_scale=0.2),
        paper_broker=PaperBroker(starting_cash=1000, trading_fee_pct=0.0, slippage_pct=0.0, min_order_notional=0.0),
    )

    result = service.run("trend_following", _build_threshold_near_miss_candles())

    meta = result["signal"]["meta"]
    assert meta["is_near_miss"] is True
    assert meta["category"] == "threshold"
    assert meta["stage"] == "route_filter"
    assert "trend_gap_pct" in meta
    assert "buy_threshold_pct" in meta


def test_run_history_persists_near_miss_signal_meta(tmp_path):
    history = RunHistoryService(store=RunHistoryStore(str(tmp_path / "run_history.json")))
    service = TradingCycleService(
        risk_controller=RiskController(max_confidence_position_scale=0.2),
        paper_broker=PaperBroker(starting_cash=1000, trading_fee_pct=0.0, slippage_pct=0.0, min_order_notional=0.0),
    )

    result = service.run("trend_following", _build_threshold_near_miss_candles())
    history.record(kind="dry_run_cycle", payload=result)

    saved = history.list_recent(limit=1)[0]
    meta = saved["payload"]["signal"]["meta"]
    assert meta["is_near_miss"] is True
    assert meta["category"] == "threshold"
    assert meta["stage"] == "route_filter"
    assert meta["block_reason"] == "sideway_filter_blocked"


def test_executor_cycle_payload_can_store_result_level_near_miss(tmp_path):
    history = RunHistoryService(store=RunHistoryStore(str(tmp_path / "run_history.json")))
    service = TradingCycleService(
        risk_controller=RiskController(max_confidence_position_scale=0.2),
        paper_broker=PaperBroker(starting_cash=1000, trading_fee_pct=0.0, slippage_pct=0.0, min_order_notional=0.0),
    )
    result = service.run("trend_following", _build_threshold_near_miss_candles())

    history.record(
        kind="executor_cycle",
        payload={
            "timestamp": "2026-04-12T14:00:00+00:00",
            "symbols_processed": 1,
            "results_count": 1,
            "results": [
                {
                    "symbol": "BTC/KRW",
                    "strategy": "trend_following",
                    "signal": result["signal"],
                    "broker_result": result["broker_result"],
                }
            ],
            "portfolio_after": result["portfolio"],
        },
    )

    saved = history.list_recent(limit=1)[0]
    meta = saved["payload"]["results"][0]["signal"]["meta"]
    assert meta["is_near_miss"] is True
    assert meta["category"] == "threshold"
