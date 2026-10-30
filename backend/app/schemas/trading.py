from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

from backend.app.schemas.simulation_run import RunStatus


class OrderRead(BaseModel):
    id: int
    run_id: int
    participant_id: int
    instrument_id: int
    sequence_number: int
    step: int
    side: Literal["BUY", "SELL"]
    status: Literal["open", "partial", "filled", "cancelled", "rejected"]
    price: Decimal
    volume: Decimal
    remaining_volume: Decimal
    reserved_amount: Decimal
    rejection_reason: str | None
    model_config = ConfigDict(from_attributes=True)


class TradeRead(BaseModel):
    id: int
    run_id: int
    instrument_id: int
    buy_order_id: int
    sell_order_id: int
    sequence_number: int
    step: int
    price: Decimal
    volume: Decimal
    quote_amount: Decimal
    model_config = ConfigDict(from_attributes=True)


class OrderBookRead(BaseModel):
    run_id: int
    instrument_id: int
    last_price: Decimal
    bids: list[OrderRead]
    asks: list[OrderRead]


class BalanceRead(BaseModel):
    asset_id: int
    available: Decimal
    reserved: Decimal
    model_config = ConfigDict(from_attributes=True)


class ParticipantRead(BaseModel):
    id: int
    sequence_number: int
    participant_type: str
    balances: list[BalanceRead]
    model_config = ConfigDict(from_attributes=True)


class SimulationResultsRead(BaseModel):
    run_id: int
    status: RunStatus
    error_message: str | None
    current_step: int
    total_steps: int
    quote_asset_id: int
    test_participant_id: int
    initial_portfolio_value: Decimal
    portfolio_value: Decimal
    profit: Decimal
    return_pct: Decimal | None
    trade_count: int
    test_trade_count: int
    balances: list[BalanceRead]
