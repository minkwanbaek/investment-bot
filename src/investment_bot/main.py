from fastapi import FastAPI
from investment_bot.api.routes import router

app = FastAPI(title="Investment Bot", version="0.1.0")
app.include_router(router)
