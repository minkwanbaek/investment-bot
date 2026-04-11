from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from investment_bot.core.settings import get_settings
from investment_bot.models.market import Candle
from investment_bot.services.container import get_account_service, get_alert_service, get_auto_trade_service, get_backtest_service, get_config_service, get_exchange_rules_service, get_live_execution_service, get_market_data_service, get_paper_broker, get_run_history_service, get_scheduler_service, get_semi_live_service, get_shadow_service, get_trading_cycle_service, get_upbit_client, get_visualization_service, get_drift_report_service
from investment_bot.strategies.registry import list_enabled_strategies, list_registered_strategies

from .dashboard import router as dashboard_router

router = APIRouter()
router.include_router(dashboard_router)


class DryRunCycleRequest(BaseModel):
    strategy_name: str
    candles: list[Candle] = Field(min_length=1)


class SeedMarketDataRequest(BaseModel):
    symbol: str
    timeframe: str = "1h"
    candles: list[Candle] = Field(min_length=1)


class AdapterCycleRequest(BaseModel):
    strategy_name: str
    adapter_name: str
    symbol: str
    timeframe: str = "1h"
    limit: int = Field(default=5, ge=1, le=500)


class ReplayAdvanceRequest(BaseModel):
    symbol: str
    timeframe: str = "1h"
    steps: int = Field(default=1, ge=1, le=500)


class ReplayBacktestRequest(BaseModel):
    strategy_name: str
    symbol: str
    timeframe: str = "1h"
    window: int = Field(default=5, ge=1, le=500)
    steps: int = Field(default=1, ge=1, le=500)


class SemiLiveCycleRequest(BaseModel):
    strategy_name: str
    symbol: str
    timeframe: str = "1h"
    limit: int = Field(default=5, ge=1, le=500)


class SemiLiveBatchRequest(BaseModel):
    strategy_name: str
    symbol: str
    timeframe: str = "1h"
    limit: int = Field(default=5, ge=1, le=500)
    iterations: int = Field(default=2, ge=1, le=20)
    interval_seconds: float = Field(default=0.0, ge=0.0, le=10.0)


class ShadowCycleRequest(BaseModel):
    strategy_name: str
    symbol: str
    timeframe: str = "1h"
    limit: int = Field(default=5, ge=1, le=500)


class LiveOrderPreviewRequest(BaseModel):
    symbol: str
    side: str
    price: float = Field(gt=0)
    volume: float = Field(gt=0)


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.environment,
        "mode": settings.trading_mode,
        "base_currency": settings.base_currency,
        "symbols": settings.symbols,
    }


@router.get("/config")
def config() -> dict:
    settings = get_settings()
    return settings.model_dump()


@router.get("/config/validate")
def validate_config() -> dict:
    return get_config_service().validate()


@router.get("/dashboard", response_class=FileResponse)
def dashboard() -> FileResponse:
    dashboard_path = Path(__file__).resolve().parent.parent / "static" / "dashboard.html"
    return FileResponse(dashboard_path)


@router.get("/strategies")
def strategies() -> dict:
    return {
        "registered": list_registered_strategies(),
        "enabled": list_enabled_strategies(),
    }


@router.get("/paper/portfolio")
def paper_portfolio() -> dict:
    portfolio = get_paper_broker().portfolio_snapshot()
    return {
        "portfolio": portfolio,
        "alerts": get_alert_service().evaluate_portfolio(portfolio),
    }


@router.get("/paper/export")
def export_paper_state() -> dict:
    return get_paper_broker().export_state()


@router.post("/paper/reset")
def reset_paper_state() -> dict:
    portfolio = get_paper_broker().reset()
    return {
        "status": "reset",
        "portfolio": portfolio,
    }


@router.get("/market-data/adapters")
def market_data_adapters() -> dict:
    return {"adapters": get_market_data_service().list_adapters()}


@router.get("/exchange/upbit/status")
def upbit_status() -> dict:
    client = get_upbit_client()
    return {"exchange": "upbit", "configured": client.configured()}


@router.get("/exchange/upbit/markets")
def upbit_markets() -> dict:
    try:
        markets = get_upbit_client().get_markets()
        payload = {"exchange": "upbit", "count": len(markets), "markets": markets}
        get_run_history_service().record(kind="upbit_markets", payload=payload)
        return payload
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/exchange/upbit/balances")
def upbit_balances() -> dict:
    try:
        balances = get_upbit_client().get_balances()
        payload = {"exchange": "upbit", "count": len(balances), "balances": balances}
        get_run_history_service().record(kind="upbit_balances", payload={"exchange": "upbit", "count": len(balances)})
        return payload
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/exchange/upbit/account-summary")
def upbit_account_summary() -> dict:
    try:
        payload = get_account_service().summarize_upbit_balances()
        get_run_history_service().record(kind="upbit_account_summary", payload={"exchange": "upbit", "asset_count": payload["asset_count"]})
        return payload
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/exchange/upbit/rules")
def upbit_rules(symbol: str = "BTC/KRW") -> dict:
    try:
        payload = get_exchange_rules_service().get_upbit_market_rules(symbol=symbol)
        get_run_history_service().record(kind="upbit_rules", payload={"exchange": "upbit", "symbol": symbol})
        return payload
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/exchange/upbit/normalize-price")
def upbit_normalize_price(symbol: str = "BTC/KRW", price: float = 0.0) -> dict:
    try:
        return get_exchange_rules_service().normalize_upbit_price(symbol=symbol, price=price)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/market-data/live/test")
def test_live_market_data(symbol: str = "BTC/KRW", timeframe: str = "1h", limit: int = 3) -> dict:
    try:
        candles = get_market_data_service().get_recent_candles(
            adapter_name="live",
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
        )
        payload = {
            "adapter": "live",
            "symbol": symbol,
            "timeframe": timeframe,
            "count": len(candles),
            "candles": [c.model_dump() for c in candles],
        }
        get_run_history_service().record(kind="live_market_test", payload=payload)
        return payload
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/market-data/mock/seed")
def seed_mock_market_data(request: SeedMarketDataRequest) -> dict:
    try:
        return get_market_data_service().seed_mock(
            symbol=request.symbol,
            timeframe=request.timeframe,
            candles=request.candles,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/market-data/replay/load")
def load_replay_market_data(request: SeedMarketDataRequest) -> dict:
    try:
        return get_market_data_service().load_replay(
            symbol=request.symbol,
            timeframe=request.timeframe,
            candles=request.candles,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/market-data/replay/advance")
def advance_replay_market_data(request: ReplayAdvanceRequest) -> dict:
    try:
        return get_market_data_service().advance_replay(
            symbol=request.symbol,
            timeframe=request.timeframe,
            steps=request.steps,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/market-data/stored")
def stored_market_data(symbol: str, timeframe: str, limit: int = 100) -> dict:
    try:
        candles = get_market_data_service().get_stored_candles(symbol=symbol, timeframe=timeframe, limit=limit)
        return {"symbol": symbol, "timeframe": timeframe, "count": len(candles), "candles": [c.model_dump() for c in candles]}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/market-data/stored/export")
def export_stored_market_data() -> dict:
    try:
        return get_market_data_service().export_candle_store()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/market-data/stored/reset")
def reset_stored_market_data() -> dict:
    try:
        return get_market_data_service().reset_candle_store()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/cycle/dry-run")
def dry_run_cycle(request: DryRunCycleRequest) -> dict:
    service = get_trading_cycle_service()
    try:
        result = service.run(strategy_name=request.strategy_name, candles=request.candles)
        get_run_history_service().record(kind="dry_run_cycle", payload=result)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/cycle/from-adapter")
def run_cycle_from_adapter(request: AdapterCycleRequest) -> dict:
    service = get_trading_cycle_service()
    market_data_service = get_market_data_service()
    try:
        candles = market_data_service.get_recent_candles(
            adapter_name=request.adapter_name,
            symbol=request.symbol,
            timeframe=request.timeframe,
            limit=request.limit,
        )
        result = {
            "adapter": request.adapter_name,
            "symbol": request.symbol,
            "timeframe": request.timeframe,
            "limit": request.limit,
            **service.run(strategy_name=request.strategy_name, candles=candles),
        }
        get_run_history_service().record(kind="adapter_cycle", payload=result)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/backtest/replay")
def run_replay_backtest(request: ReplayBacktestRequest) -> dict:
    try:
        result = get_backtest_service().run_replay(
            strategy_name=request.strategy_name,
            symbol=request.symbol,
            timeframe=request.timeframe,
            window=request.window,
            steps=request.steps,
        )
        get_run_history_service().record(kind="replay_backtest", payload=result)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/cycle/semi-live")
def run_semi_live_cycle(request: SemiLiveCycleRequest) -> dict:
    try:
        return get_semi_live_service().run_once(
            strategy_name=request.strategy_name,
            symbol=request.symbol,
            timeframe=request.timeframe,
            limit=request.limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/cycle/semi-live/batch")
def run_semi_live_batch(request: SemiLiveBatchRequest) -> dict:
    try:
        return get_scheduler_service().run_semi_live_batch(
            strategy_name=request.strategy_name,
            symbol=request.symbol,
            timeframe=request.timeframe,
            limit=request.limit,
            iterations=request.iterations,
            interval_seconds=request.interval_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/cycle/shadow")
def run_shadow_cycle(request: ShadowCycleRequest) -> dict:
    try:
        return get_shadow_service().run_once(
            strategy_name=request.strategy_name,
            symbol=request.symbol,
            timeframe=request.timeframe,
            limit=request.limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/exchange/upbit/orders/preview")
def preview_upbit_order(request: LiveOrderPreviewRequest) -> dict:
    try:
        return get_live_execution_service().preview_order(
            symbol=request.symbol,
            side=request.side,
            price=request.price,
            volume=request.volume,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/exchange/upbit/orders/submit")
def submit_upbit_order(request: LiveOrderPreviewRequest) -> dict:
    try:
        return get_live_execution_service().submit_order(
            symbol=request.symbol,
            side=request.side,
            price=request.price,
            volume=request.volume,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/runs")
def list_recent_runs(limit: int = 20) -> dict:
    return {"runs": get_run_history_service().list_recent(limit=limit)}


@router.get("/runs/summary")
def summarize_recent_runs(limit: int = 20) -> dict:
    return get_run_history_service().summarize_recent(limit=limit)


@router.get("/operator/drift-report")
def operator_drift_report(limit: int = 50) -> dict:
    return get_drift_report_service().summarize(limit=limit)


@router.get("/operator/live-dashboard")
def operator_live_dashboard(limit: int = 20) -> dict:
    recent_runs = get_run_history_service().list_recent(limit=limit)
    return {
        "health": health(),
        "summary": get_run_history_service().summarize_recent(limit=limit),
        "paper_portfolio": paper_portfolio(),
        "profit_structure": get_visualization_service().summarize_profit_structure(limit=max(limit, 10)),
        "drift_report": get_drift_report_service().summarize(limit=max(limit, 10)),
        "auto_trade": get_auto_trade_service().status(),
        "recent_runs": recent_runs,
        "latest_run": recent_runs[-1] if recent_runs else None,
    }


@router.get("/auto-trade/status")
def auto_trade_status() -> dict:
    return get_auto_trade_service().status()


@router.post("/auto-trade/start")
def auto_trade_start() -> dict:
    return get_auto_trade_service().start()


@router.post("/auto-trade/stop")
def auto_trade_stop() -> dict:
    return get_auto_trade_service().stop()


@router.post("/auto-trade/run-once")
def auto_trade_run_once() -> dict:
    return get_auto_trade_service().run_once()


@router.get("/visualizations/profit-structure")
def profit_structure_visualization(limit: int = 50) -> dict:
    return get_visualization_service().summarize_profit_structure(limit=limit)


@router.post("/runs/reset")
def reset_runs() -> dict:
    return get_run_history_service().reset()
