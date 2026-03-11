from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from investment_bot.core.settings import get_settings
from investment_bot.models.market import Candle
from investment_bot.services.container import get_paper_broker, get_trading_cycle_service
from investment_bot.strategies.registry import list_enabled_strategies, list_registered_strategies

router = APIRouter()


class DryRunCycleRequest(BaseModel):
    strategy_name: str
    candles: list[Candle] = Field(min_length=1)


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


@router.get("/strategies")
def strategies() -> dict:
    return {
        "registered": list_registered_strategies(),
        "enabled": list_enabled_strategies(),
    }


@router.get("/paper/portfolio")
def paper_portfolio() -> dict:
    return get_paper_broker().portfolio_snapshot()


@router.post("/cycle/dry-run")
def dry_run_cycle(request: DryRunCycleRequest) -> dict:
    service = get_trading_cycle_service()
    try:
        return service.run(strategy_name=request.strategy_name, candles=request.candles)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
