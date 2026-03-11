from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from investment_bot.core.settings import get_settings
from investment_bot.models.market import Candle
from investment_bot.services.container import get_alert_service, get_backtest_service, get_config_service, get_market_data_service, get_paper_broker, get_trading_cycle_service
from investment_bot.strategies.registry import list_enabled_strategies, list_registered_strategies

router = APIRouter()


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


@router.get("/market-data/adapters")
def market_data_adapters() -> dict:
    return {"adapters": get_market_data_service().list_adapters()}


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


@router.post("/cycle/dry-run")
def dry_run_cycle(request: DryRunCycleRequest) -> dict:
    service = get_trading_cycle_service()
    try:
        return service.run(strategy_name=request.strategy_name, candles=request.candles)
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
        result = service.run(strategy_name=request.strategy_name, candles=candles)
        return {
            "adapter": request.adapter_name,
            "symbol": request.symbol,
            "timeframe": request.timeframe,
            "limit": request.limit,
            **result,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/backtest/replay")
def run_replay_backtest(request: ReplayBacktestRequest) -> dict:
    try:
        return get_backtest_service().run_replay(
            strategy_name=request.strategy_name,
            symbol=request.symbol,
            timeframe=request.timeframe,
            window=request.window,
            steps=request.steps,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
