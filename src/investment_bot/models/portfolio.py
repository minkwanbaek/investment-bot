from pydantic import BaseModel, Field


class PositionSnapshot(BaseModel):
    symbol: str
    quantity: float = Field(ge=0)
    average_price: float = Field(ge=0)
    market_price: float = Field(ge=0)
    market_value: float
    cost_basis: float = Field(ge=0)
    unrealized_pnl: float
    realized_pnl: float


class PortfolioSnapshot(BaseModel):
    cash_balance: float
    starting_cash: float
    positions: dict[str, PositionSnapshot]
    order_count: int = Field(ge=0)
    total_equity: float
    total_realized_pnl: float
    total_unrealized_pnl: float
