from typing import Literal
from pydantic import BaseModel, Field


class PaperOrder(BaseModel):
    strategy_name: str
    symbol: str
    action: Literal["buy", "sell"]
    confidence: float = Field(ge=0, le=1)
    requested_size: float = Field(ge=0)
    approved_size: float = Field(ge=0)
    execution_price: float = Field(gt=0)
    notional_value: float = Field(ge=0)
    reason: str
    status: Literal["recorded"] = "recorded"
