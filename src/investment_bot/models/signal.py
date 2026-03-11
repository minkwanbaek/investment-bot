from typing import Literal
from pydantic import BaseModel, Field

class TradeSignal(BaseModel):
    strategy_name: str
    symbol: str
    action: Literal["buy", "sell", "hold"]
    confidence: float = Field(ge=0, le=1)
    reason: str
