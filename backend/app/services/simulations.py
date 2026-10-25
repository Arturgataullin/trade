from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app.models.instrument import Instrument
from backend.app.models.simulation import (
    BackgroundStrategyProfile,
    Simulation,
    SimulationInstrument,
    TestStrategy,
)
from backend.app.models.simulation_run import SimulationRun
from backend.app.schemas.simulation import SimulationWrite, StrategyParameters


class SimulationNotFoundError(Exception):
    """Raised when a user does not own the requested simulation."""


class InvalidSimulationConfigurationError(Exception):
    """Raised when referenced instruments cannot form a valid market."""


class SimulationRunningError(Exception):
    """Raised when a running experiment configuration is edited."""


def _decimal(value: float) -> Decimal:
    return Decimal(str(value))


def _simulation_options():
    return (
        selectinload(Simulation.instrument_configs)
        .selectinload(SimulationInstrument.instrument)
        .selectinload(Instrument.base_asset),
        selectinload(Simulation.instrument_configs)
        .selectinload(SimulationInstrument.instrument)
        .selectinload(Instrument.quote_asset),
        selectinload(Simulation.background_profiles),
        selectinload(Simulation.test_strategy),
    )


def list_simulations(db: Session, owner_id: int) -> list[Simulation]:
    statement = (
        select(Simulation)
        .where(Simulation.owner_id == owner_id)
        .options(*_simulation_options())
        .order_by(Simulation.updated_at.desc(), Simulation.id.desc())
    )
    return list(db.scalars(statement).unique().all())


def get_simulation(db: Session, simulation_id: int, owner_id: int) -> Simulation:
    statement = (
        select(Simulation)
        .where(
            Simulation.id == simulation_id,
            Simulation.owner_id == owner_id,
        )
        .options(*_simulation_options())
    )
    simulation = db.scalar(statement)
    if simulation is None:
        raise SimulationNotFoundError
    return simulation


def create_simulation(
    db: Session,
    owner_id: int,
    data: SimulationWrite,
) -> Simulation:
    instruments = _validate_instruments(db, data)
    simulation = Simulation(owner_id=owner_id)
    _apply_configuration(simulation, data, instruments)
    db.add(simulation)
    db.commit()
    return get_simulation(db, simulation.id, owner_id)


def update_simulation(
    db: Session,
    simulation_id: int,
    owner_id: int,
    data: SimulationWrite,
) -> Simulation:
    simulation = get_simulation(db, simulation_id, owner_id)
    active_run_id = db.scalar(
        select(SimulationRun.id).where(
            SimulationRun.simulation_id == simulation_id,
            SimulationRun.status == "running",
        )
    )
    if active_run_id is not None:
        raise SimulationRunningError

    instruments = _validate_instruments(db, data)

    simulation.instrument_configs.clear()
    simulation.background_profiles.clear()
    simulation.test_strategy = None
    db.flush()

    _apply_configuration(simulation, data, instruments)
    db.commit()
    return get_simulation(db, simulation.id, owner_id)


def _validate_instruments(
    db: Session,
    data: SimulationWrite,
) -> dict[int, Instrument]:
    instrument_ids = [item.instrument_id for item in data.instrument_configs]
    statement = (
        select(Instrument)
        .where(
            Instrument.id.in_(instrument_ids),
            Instrument.is_active.is_(True),
        )
        .options(
            selectinload(Instrument.base_asset),
            selectinload(Instrument.quote_asset),
        )
    )
    instruments = {item.id: item for item in db.scalars(statement).all()}

    if len(instruments) != len(instrument_ids):
        raise InvalidSimulationConfigurationError(
            "Every selected trading instrument must exist and be active"
        )
    if any(
        not item.base_asset.is_active or not item.quote_asset.is_active
        for item in instruments.values()
    ):
        raise InvalidSimulationConfigurationError(
            "Selected trading instruments must use active assets"
        )
    if len(instruments) == 2:
        quote_asset_ids = {item.quote_asset_id for item in instruments.values()}
        if len(quote_asset_ids) != 1:
            raise InvalidSimulationConfigurationError(
                "Two trading instruments must have the same quote asset"
            )

    return instruments


def _apply_configuration(
    simulation: Simulation,
    data: SimulationWrite,
    instruments: dict[int, Instrument],
) -> None:
    simulation.name = data.name
    simulation.duration_steps = data.duration_steps
    simulation.seed = data.seed
    simulation.background_initial_quote_balance = _decimal(
        data.background_initial_quote_balance
    )
    simulation.background_min_order_volume = _decimal(
        data.background_min_order_volume
    )
    simulation.background_max_order_volume = _decimal(
        data.background_max_order_volume
    )
    simulation.test_initial_quote_balance = _decimal(
        data.test_initial_quote_balance
    )
    simulation.test_min_order_volume = _decimal(data.test_min_order_volume)
    simulation.test_max_order_volume = _decimal(data.test_max_order_volume)

    simulation.instrument_configs = [
        SimulationInstrument(
            instrument=instruments[item.instrument_id],
            initial_price=_decimal(item.initial_price),
            background_initial_base_balance=_decimal(
                item.background_initial_base_balance
            ),
            test_initial_base_balance=_decimal(item.test_initial_base_balance),
        )
        for item in data.instrument_configs
    ]
    simulation.background_profiles = [
        BackgroundStrategyProfile(
            agent_count=item.agent_count,
            **_strategy_values(item),
        )
        for item in data.background_profiles
    ]
    simulation.test_strategy = TestStrategy(**_strategy_values(data.test_strategy))


def _strategy_values(data: StrategyParameters) -> dict[str, object]:
    return {
        "strategy_type": data.strategy_type,
        "buy_probability": (
            _decimal(data.buy_probability)
            if data.buy_probability is not None
            else None
        ),
        "sell_probability": (
            _decimal(data.sell_probability)
            if data.sell_probability is not None
            else None
        ),
        "hold_probability": (
            _decimal(data.hold_probability)
            if data.hold_probability is not None
            else None
        ),
        "price_deviation_pct": (
            _decimal(data.price_deviation_pct)
            if data.price_deviation_pct is not None
            else None
        ),
        "trend_window": data.trend_window,
        "trend_threshold_pct": (
            _decimal(data.trend_threshold_pct)
            if data.trend_threshold_pct is not None
            else None
        ),
    }
