from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from investment_bot.api.routes import router
from investment_bot.services.container import get_auto_trade_service, get_settings

app = FastAPI(title="Trading Bot", version="0.1.0")
app.include_router(router)
app.mount("/static", StaticFiles(directory=Path(__file__).resolve().parent / "static"), name="static")


@app.on_event("startup")
def startup_auto_trade() -> None:
    import logging
    logger = logging.getLogger("uvicorn")
    settings = get_settings()
    logger.info("startup_auto_trade: auto_trade_enabled=%s", settings.auto_trade_enabled)
    if settings.auto_trade_enabled:
        service = get_auto_trade_service()
        logger.info("startup_auto_trade: service.active=%s before start", service.active)
        if not service.active:
            result = service.start()
            logger.info("startup_auto_trade: start() result=%s", result)
