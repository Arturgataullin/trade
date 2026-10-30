"""Trading operations. The caller commits or rolls back the entire transaction.

All writers must lock the run first, including the simulation worker and stop
handler. PostgreSQL serializes operations within a run through this row lock.
"""

from decimal import Decimal, ROUND_CEILING, ROUND_DOWN, localcontext

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models.simulation_run import (
    ParticipantBalance,
    SimulationParticipant,
    SimulationRun,
    SimulationRunInstrument,
)
from backend.app.models.trading import Order, Trade


QUANTUM = Decimal("0.00000001")
MAX_AMOUNT = Decimal("10000000000000000")
ACTIVE_STATUSES = ("open", "partial")


class TradingError(ValueError):
    """Invalid trading operation; the caller should roll back the transaction."""


def lock_run(db: Session, run_id: int) -> SimulationRun:
    run = db.scalar(
        select(SimulationRun)
        .where(SimulationRun.id == run_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if run is None:
        raise TradingError("Run not found")
    return run


def place_order(
    db: Session,
    run_id: int,
    participant_id: int,
    instrument_id: int,
    side: str,
    price: Decimal,
    volume: Decimal,
    step: int,
) -> Order:
    run = lock_run(db, run_id)
    if run.status != "running" or run.stop_requested:
        raise TradingError("Run is not running")
    if side not in ("BUY", "SELL"):
        raise TradingError("Side must be BUY or SELL")
    if step < run.current_step or step > run.total_steps:
        raise TradingError("Invalid model step")
    price = _positive_amount(price)
    volume = _positive_amount(volume)
    market = db.scalar(
        select(SimulationRunInstrument).where(
            SimulationRunInstrument.run_id == run_id,
            SimulationRunInstrument.instrument_id == instrument_id,
        )
    )
    participant = db.scalar(
        select(SimulationParticipant).where(
            SimulationParticipant.id == participant_id,
            SimulationParticipant.run_id == run_id,
        )
    )
    if market is None or participant is None:
        raise TradingError("Participant and instrument must belong to the run")

    instrument = market.instrument
    asset_id = instrument.quote_asset_id if side == "BUY" else instrument.base_asset_id
    balance = _balance(db, participant_id, asset_id)
    reserve = _buy_reserve(price, volume) if side == "BUY" else volume
    if _cost(price, volume, ROUND_DOWN) == 0:
        raise TradingError("Order value must be at least 0.00000001")
    if reserve >= MAX_AMOUNT:
        raise TradingError("Order value exceeds balance precision")

    order = Order(
        run_id=run_id,
        participant_id=participant_id,
        instrument_id=instrument_id,
        sequence_number=_next_sequence(db, Order, run_id),
        step=step,
        side=side,
        status="open",
        price=price,
        volume=volume,
        remaining_volume=volume,
        reserved_amount=Decimal("0"),
    )
    if balance.available < reserve:
        order.status = "rejected"
        order.rejection_reason = "Insufficient available balance"
    else:
        balance.available -= reserve
        balance.reserved += reserve
        order.reserved_amount = reserve

    db.add(order)
    db.flush()
    if order.status == "rejected":
        return order

    _match(db, order, market)
    db.flush()
    return order


def cancel_order(db: Session, run_id: int, order_id: int) -> Order:
    lock_run(db, run_id)
    order = db.scalar(select(Order).where(
        Order.id == order_id, Order.run_id == run_id
    ).execution_options(populate_existing=True))
    if order is None:
        raise TradingError("Order not found in this run")
    if order.status not in ACTIVE_STATUSES:
        return order

    market = db.scalar(
        select(SimulationRunInstrument).where(
            SimulationRunInstrument.run_id == run_id,
            SimulationRunInstrument.instrument_id == order.instrument_id,
        )
    )
    instrument = market.instrument
    asset_id = instrument.quote_asset_id if order.side == "BUY" else instrument.base_asset_id
    balance = _balance(db, order.participant_id, asset_id)
    balance.reserved -= order.reserved_amount
    balance.available += order.reserved_amount
    order.reserved_amount = Decimal("0")
    order.status = "cancelled"
    db.flush()
    return order


def get_order_book(
    db: Session, run_id: int, instrument_id: int, limit: int | None = None,
) -> dict[str, list[Order]]:
    common = (
        Order.run_id == run_id,
        Order.instrument_id == instrument_id,
        Order.status.in_(ACTIVE_STATUSES),
    )
    return {
        "bids": list(db.scalars(select(Order).where(*common, Order.side == "BUY").order_by(
            Order.price.desc(), Order.sequence_number
        ).limit(limit))),
        "asks": list(db.scalars(select(Order).where(*common, Order.side == "SELL").order_by(
            Order.price, Order.sequence_number
        ).limit(limit))),
    }


def get_price_history(db: Session, run_id: int, instrument_id: int) -> list[Decimal]:
    """Only executed trade prices, without the initial price (not a trade)."""
    return list(db.scalars(
        select(Trade.price).where(
            Trade.run_id == run_id, Trade.instrument_id == instrument_id
        ).order_by(Trade.sequence_number)
    ))


def _match(db: Session, incoming: Order, market: SimulationRunInstrument) -> None:
    buying = incoming.side == "BUY"
    statement = select(Order).where(
        Order.run_id == incoming.run_id,
        Order.instrument_id == incoming.instrument_id,
        Order.side == ("SELL" if buying else "BUY"),
        Order.status.in_(ACTIVE_STATUSES),
        # Self trades are skipped; the participant's own order keeps its priority.
        Order.participant_id != incoming.participant_id,
        Order.price <= incoming.price if buying else Order.price >= incoming.price,
    ).order_by(
        Order.price.asc() if buying else Order.price.desc(),
        Order.sequence_number,
    ).execution_options(populate_existing=True)
    for resting in db.scalars(statement):
        if incoming.remaining_volume == 0:
            break
        volume = min(incoming.remaining_volume, resting.remaining_volume)
        # A dust remainder smaller than the quote precision stays in the book.
        if _cost(resting.price, volume, ROUND_DOWN) == 0:
            continue
        buy, sell = (incoming, resting) if buying else (resting, incoming)
        _settle(db, buy, sell, resting.price, volume, market, incoming.step)


def _settle(
    db: Session,
    buy: Order,
    sell: Order,
    price: Decimal,
    volume: Decimal,
    market: SimulationRunInstrument,
    step: int,
) -> None:
    instrument = market.instrument
    buyer_quote = _balance(db, buy.participant_id, instrument.quote_asset_id)
    buyer_base = _balance(db, buy.participant_id, instrument.base_asset_id)
    seller_quote = _balance(db, sell.participant_id, instrument.quote_asset_id)
    seller_base = _balance(db, sell.participant_id, instrument.base_asset_id)

    # Settlement is rounded down to the quote asset's 8 decimal places.
    # Reservation rounds up, so even partial fills remain fully funded.
    quote_amount = _cost(price, volume, ROUND_DOWN)
    remaining_buy_volume = buy.remaining_volume - volume
    remaining_reserve = _buy_reserve(buy.price, remaining_buy_volume)
    released = buy.reserved_amount - remaining_reserve
    buyer_quote.reserved -= released
    buyer_quote.available += released - quote_amount
    buyer_base.available += volume
    seller_base.reserved -= volume
    seller_quote.available += quote_amount

    buy.remaining_volume = remaining_buy_volume
    buy.reserved_amount = remaining_reserve
    sell.remaining_volume -= volume
    sell.reserved_amount -= volume
    for order in (buy, sell):
        order.status = "filled" if order.remaining_volume == 0 else "partial"

    db.add(Trade(
        run_id=buy.run_id,
        instrument_id=buy.instrument_id,
        buy_order_id=buy.id,
        sell_order_id=sell.id,
        sequence_number=_next_sequence(db, Trade, buy.run_id),
        step=step,
        price=price,
        volume=volume,
        quote_amount=quote_amount,
    ))
    market.last_price = price
    # Make each execution visible to the next sequence query with autoflush=False.
    db.flush()


def _balance(db: Session, participant_id: int, asset_id: int) -> ParticipantBalance:
    balance = db.scalar(select(ParticipantBalance).where(
        ParticipantBalance.participant_id == participant_id,
        ParticipantBalance.asset_id == asset_id,
    ).execution_options(populate_existing=True))
    if balance is None:
        raise TradingError("Participant balance is missing")
    return balance


def _next_sequence(db: Session, model: type[Order] | type[Trade], run_id: int) -> int:
    return (db.scalar(select(func.max(model.sequence_number)).where(model.run_id == run_id)) or 0) + 1


def _positive_amount(value: Decimal) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise TradingError("Amounts must be finite Decimal values")
    if value <= 0 or value >= MAX_AMOUNT or value.as_tuple().exponent < -8:
        raise TradingError("Amount must be positive and have at most 8 decimal places")
    return value


def _cost(price: Decimal, volume: Decimal, rounding: str) -> Decimal:
    with localcontext() as context:
        context.prec = 60
        return (price * volume).quantize(QUANTUM, rounding=rounding)


def _buy_reserve(price: Decimal, volume: Decimal) -> Decimal:
    return _cost(price, volume, ROUND_CEILING)
