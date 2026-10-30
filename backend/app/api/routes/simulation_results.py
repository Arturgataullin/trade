from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.app.api.dependencies import CurrentUser, DbSession
from backend.app.models import Order, SimulationParticipant, SimulationRun, Trade
from backend.app.schemas.trading import (
    OrderBookRead, OrderRead, ParticipantRead, SimulationResultsRead, TradeRead,
)
from backend.app.services.simulation_results import (
    calculate_results, get_owned_run, get_run_market,
)
from backend.app.services.simulations import SimulationNotFoundError
from backend.app.services.trading import get_order_book


router = APIRouter(prefix="/simulations", tags=["simulation results"])


def owned_run(
    simulation_id: int, db: DbSession, current_user: CurrentUser,
    run_id: int | None = Query(default=None, gt=0),
) -> SimulationRun:
    try:
        return get_owned_run(db, simulation_id, current_user.id, run_id)
    except SimulationNotFoundError as exc:
        raise HTTPException(404, "Experiment or run not found") from exc


OwnedRun = Annotated[SimulationRun, Depends(owned_run)]
PageSize = Annotated[int, Query(ge=1, le=1000)]


def require_market(db, run, instrument_id):
    try:
        return get_run_market(db, run.id, instrument_id)
    except SimulationNotFoundError as exc:
        raise HTTPException(404, "Instrument not found in this run") from exc


@router.get("/{simulation_id}/order-book", response_model=OrderBookRead)
def read_order_book(
    db: DbSession, run: OwnedRun, instrument_id: int, limit: PageSize = 50,
):
    market = require_market(db, run, instrument_id)
    book = get_order_book(db, run.id, instrument_id, limit=limit)
    return OrderBookRead(
        run_id=run.id, instrument_id=instrument_id, last_price=market.last_price,
        bids=[OrderRead.model_validate(o) for o in book["bids"]],
        asks=[OrderRead.model_validate(o) for o in book["asks"]],
    )


@router.get("/{simulation_id}/trades", response_model=list[TradeRead])
def read_trades(
    db: DbSession, run: OwnedRun, instrument_id: int | None = None,
    after: int = Query(default=0, ge=0), limit: PageSize = 100,
):
    statement = select(Trade).where(Trade.run_id == run.id, Trade.sequence_number > after)
    if instrument_id is not None:
        require_market(db, run, instrument_id)
        statement = statement.where(Trade.instrument_id == instrument_id)
    return [TradeRead.model_validate(t) for t in db.scalars(
        statement.order_by(Trade.sequence_number).limit(limit)
    )]


@router.get("/{simulation_id}/orders", response_model=list[OrderRead])
def read_orders(
    db: DbSession, run: OwnedRun, instrument_id: int | None = None,
    after: int = Query(default=0, ge=0), limit: PageSize = 100,
):
    statement = select(Order).where(Order.run_id == run.id, Order.sequence_number > after)
    if instrument_id is not None:
        require_market(db, run, instrument_id)
        statement = statement.where(Order.instrument_id == instrument_id)
    return [OrderRead.model_validate(o) for o in db.scalars(
        statement.order_by(Order.sequence_number).limit(limit)
    )]


@router.get("/{simulation_id}/balances", response_model=list[ParticipantRead])
def read_balances(
    db: DbSession, run: OwnedRun, after: int = Query(default=0, ge=0),
    limit: PageSize = 100,
):
    return [ParticipantRead.model_validate(p) for p in db.scalars(
        select(SimulationParticipant).where(
            SimulationParticipant.run_id == run.id,
            SimulationParticipant.sequence_number > after,
        ).options(selectinload(SimulationParticipant.balances))
         .order_by(SimulationParticipant.sequence_number).limit(limit)
    )]


@router.get("/{simulation_id}/results", response_model=SimulationResultsRead)
def read_results(db: DbSession, run: OwnedRun):
    return calculate_results(db, run)
