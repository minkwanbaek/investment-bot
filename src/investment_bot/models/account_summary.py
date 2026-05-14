from enum import StrEnum

from pydantic import BaseModel, Field


class SellBlockReason(StrEnum):
    BELOW_MIN_ORDER_NOTIONAL = "below_min_order_notional"
    INACTIVE_MARKET = "inactive_market"
    NO_TICKER = "no_ticker"
    INSUFFICIENT_BALANCE = "insufficient_balance"


class AccountAssetSummary(BaseModel):
    currency: str
    balance: float = Field(ge=0)
    market_value: float | None = Field(default=None, ge=0)
    liquidation_value: float | None = Field(default=None, ge=0)
    sellable_now: bool
    sell_block_reason: SellBlockReason | None = None


class UpbitAccountSummary(BaseModel):
    exchange: str
    asset_count: int = Field(ge=0)
    krw_cash: float = Field(ge=0)
    assets: list[AccountAssetSummary]
