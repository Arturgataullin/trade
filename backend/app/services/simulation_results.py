from decimal import Decimal, localcontext

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, aliased, selectinload

from backend.app.models import (
    Order, Simulation, SimulationParticipant, SimulationRun,
    SimulationRunInstrument, Trade,
)
from backend.app.schemas.trading import BalanceRead, SimulationResultsRead
from backend.app.services.simulations import SimulationNotFoundError


def get_owned_run(
    db: Session, simulation_id: int, owner_id: int, run_id: int | None = None,
) -> SimulationRun:
    statement = select(SimulationRun).join(
        Simulation, Simulation.id == SimulationRun.simulation_id
    ).where(
        Simulation.id == simulation_id, Simulation.owner_id == owner_id,
    )
    if run_id is not None:
        statement = statement.where(SimulationRun.id == run_id)
    # Hold a shared lock until the response data is assembled: a consistent step.
    run = db.scalar(statement.order_by(SimulationRun.id.desc()).limit(1)
                    .with_for_update(read=True, of=SimulationRun))
    if run is None:
        raise SimulationNotFoundError
    return run


def get_run_market(db: Session, run_id: int, instrument_id: int) -> SimulationRunInstrument:
    market = db.scalar(select(SimulationRunInstrument).where(
        SimulationRunInstrument.run_id == run_id,
        SimulationRunInstrument.instrument_id == instrument_id,
    ))
    if market is None:
        raise SimulationNotFoundError
    return market


def calculate_results(db: Session, run: SimulationRun) -> SimulationResultsRead:
    participant = db.scalar(select(SimulationParticipant).where(
        SimulationParticipant.run_id == run.id,
        SimulationParticipant.participant_type == "test",
    ).options(selectinload(SimulationParticipant.balances)))
    markets = list(db.scalars(select(SimulationRunInstrument).where(
        SimulationRunInstrument.run_id == run.id
    ).order_by(SimulationRunInstrument.instrument_id)))
    if participant is None or not markets:
        raise ValueError("Run has no test participant or instruments")
    balances = {
        b.asset_id: b.available + b.reserved for b in participant.balances
    }
    quote_asset_id = markets[0].instrument.quote_asset_id
    snapshot = run.configuration_snapshot
    initial_base = {
        config["instrument_id"]: Decimal(str(config["test_initial_base_balance"]))
        for config in snapshot["instrument_configs"]
    }
    with localcontext() as context:
        context.prec = 60
        initial = Decimal(str(snapshot["test_initial_quote_balance"]))
        current = balances[quote_asset_id]
        for market in markets:
            initial += initial_base[market.instrument_id] * market.initial_price
            current += balances[market.instrument.base_asset_id] * market.last_price
        profit = current - initial
        return_pct = profit / initial * 100 if initial else None

    buy, sell = aliased(Order), aliased(Order)
    test_count = db.scalar(select(func.count(Trade.id)).join(
        buy, Trade.buy_order_id == buy.id
    ).join(sell, Trade.sell_order_id == sell.id).where(
        Trade.run_id == run.id,
        or_(buy.participant_id == participant.id, sell.participant_id == participant.id),
    ))
    return SimulationResultsRead(
        run_id=run.id, status=run.status, error_message=run.error_message,
        current_step=run.current_step, total_steps=run.total_steps,
        quote_asset_id=quote_asset_id, test_participant_id=participant.id,
        initial_portfolio_value=initial, portfolio_value=current, profit=profit,
        return_pct=return_pct,
        trade_count=db.scalar(select(func.count(Trade.id)).where(Trade.run_id == run.id)),
        test_trade_count=test_count,
        balances=[BalanceRead.model_validate(b) for b in participant.balances],
    )
