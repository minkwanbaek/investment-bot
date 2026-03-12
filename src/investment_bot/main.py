from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from investment_bot.api.routes import router

app = FastAPI(title="Trading Bot", version="0.1.0")
app.include_router(router)
app.mount("/static", StaticFiles(directory=Path(__file__).resolve().parent / "static"), name="static")
