from __future__ import annotations

from pydantic import BaseModel, Field


class PaperOrder(BaseModel):
    ticker: str
    trade_date: str
    asset_type: str = "stock"
    rating: str
    action: str
    target_position_size: float
    risk_gate_approved: bool
    source_run_id: str = ""
    thesis: str = ""
    horizon_days: int = 20


class PaperFill(BaseModel):
    ticker: str
    trade_date: str
    side: str
    rating: str = ""
    action: str = ""
    target_position_size: float = 0.0
    source_run_id: str = ""
    thesis: str = ""
    horizon_days: int = 20
    quantity: float
    price: float
    gross_amount: float
    commission: float = 0.0
    cash_after: float


class PaperPosition(BaseModel):
    ticker: str
    quantity: float = 0.0
    average_cost: float = 0.0
    last_price: float = 0.0

    @property
    def market_value(self) -> float:
        return self.quantity * self.last_price

    @property
    def unrealized_pnl(self) -> float:
        return (self.last_price - self.average_cost) * self.quantity


class PaperAccountSnapshot(BaseModel):
    trade_date: str
    cash: float
    positions_value: float
    equity: float
    total_return: float
    positions: dict[str, PaperPosition] = Field(default_factory=dict)
    price_source: str = "real"


class PaperTradingResult(BaseModel):
    ticker: str
    trade_date: str
    holding_days: int
    resolved: bool
    reason: str = ""
    order: PaperOrder | None = None
    fills: list[PaperFill] = Field(default_factory=list)
    snapshots: list[PaperAccountSnapshot] = Field(default_factory=list)
    simulation: dict = Field(default_factory=dict)
