from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


TradeSide = Literal["buy", "sell"]


class MarketRegime(str, Enum):
    TREND_UP = "trend_up"
    TREND_DOWN = "trend_down"
    SIDEWAYS = "sideways"
    UNCERTAIN = "uncertain"


class VolatilityState(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class HigherTFBias(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"



class TradeLogSchema(BaseModel):
    trade_id: str = Field(min_length=1)
    strategy_version: str | None = None
    symbol: str = Field(min_length=1)
    side: TradeSide
    entry_time: datetime
    exit_time: datetime | None = None
    entry_price: float = Field(gt=0)
    exit_price: float | None = Field(default=None, gt=0)
    quantity: float = Field(ge=0)
    gross_pnl: float | None = None
    net_pnl: float | None = None
    pnl_pct: float | None = None
    holding_seconds: float | None = Field(default=None, ge=0)
    entry_reason: str | None = None
    exit_reason: str | None = None
    market_regime: str | None = None
    volatility_state: str | None = None
    higher_tf_bias: str | None = None
