import hashlib
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.simulation import (
    BackgroundStrategyProfile,
    Simulation,
    TestStrategy,
)
from backend.app.models.simulation_run import (
    ParticipantBalance,
    SimulationParticipant,
    SimulationRun,
    SimulationRunInstrument,
)
from backend.app.schemas.simulation import SimulationRead
from backend.app.services.simulations import SimulationNotFoundError, get_simulation


ENGINE_VERSION = "1"


class SimulationAlreadyRunningError(Exception):
    """Raised when an experiment already has an active run."""


class SimulationNotRunningError(Exception):
    """Raised when there is no active run to stop."""


class SimulationCannotStartError(Exception):
    """Raised when a saved configuration is no longer runnable."""


def get_latest_run(
    db: Session,
    simulation_id: int,
    owner_id: int,
) -> SimulationRun | None:
    statement = (
        select(SimulationRun)
        .join(Simulation, Simulation.id == SimulationRun.simulation_id)
        .where(
            SimulationRun.simulation_id == simulation_id,
            Simulation.owner_id == owner_id,
        )
        .order_by(SimulationRun.id.desc())
    )
    return db.scalars(statement).first()


def start_simulation(
    db: Session,
    simulation_id: int,
    owner_id: int,
) -> SimulationRun:
    simulation = get_simulation(db, simulation_id, owner_id)
    active_run = db.scalar(
        select(SimulationRun).where(
            SimulationRun.simulation_id == simulation_id,
            SimulationRun.status == "running",
        )
    )
    if active_run is not None:
        raise SimulationAlreadyRunningError

    _validate_startable(simulation)
    snapshot = SimulationRead.model_validate(simulation).model_dump(mode="json")
    run = SimulationRun(
        simulation_id=simulation.id,
        total_steps=simulation.duration_steps,
        seed=simulation.seed,
        engine_version=ENGINE_VERSION,
        configuration_snapshot=snapshot,
    )
    run.instruments = [
        SimulationRunInstrument(
            instrument_id=config.instrument_id,
            initial_price=config.initial_price,
            last_price=config.initial_price,
        )
        for config in simulation.instrument_configs
    ]
    run.participants = _build_participants(simulation)

    db.add(run)
    db.commit()
    return _get_run(db, run.id, owner_id)


def stop_simulation(
    db: Session,
    simulation_id: int,
    owner_id: int,
) -> SimulationRun:
    simulation = get_simulation(db, simulation_id, owner_id)
    run = db.scalar(
        select(SimulationRun)
        .where(
            SimulationRun.simulation_id == simulation.id,
            SimulationRun.status == "running",
        )
        .order_by(SimulationRun.id.desc())
    )
    if run is None:
        raise SimulationNotRunningError

    run.stop_requested = True
    run.status = "stopped"
    run.finished_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)
    return run


def _get_run(db: Session, run_id: int, owner_id: int) -> SimulationRun:
    statement = (
        select(SimulationRun)
        .join(Simulation, Simulation.id == SimulationRun.simulation_id)
        .where(
            SimulationRun.id == run_id,
            Simulation.owner_id == owner_id,
        )
    )
    run = db.scalar(statement)
    if run is None:
        raise SimulationNotFoundError
    return run


def _validate_startable(simulation: Simulation) -> None:
    if not simulation.instrument_configs:
        raise SimulationCannotStartError("Experiment has no trading instruments")

    quote_asset_ids: set[int] = set()
    for config in simulation.instrument_configs:
        instrument = config.instrument
        if (
            not instrument.is_active
            or not instrument.base_asset.is_active
            or not instrument.quote_asset.is_active
        ):
            raise SimulationCannotStartError(
                "Every trading instrument and its assets must be active"
            )
        quote_asset_ids.add(instrument.quote_asset_id)

    if len(quote_asset_ids) != 1:
        raise SimulationCannotStartError(
            "Trading instruments must have the same quote asset"
        )


def _build_participants(simulation: Simulation) -> list[SimulationParticipant]:
    participants: list[SimulationParticipant] = []
    sequence_number = 1

    for profile_index, profile in enumerate(simulation.background_profiles, start=1):
        for _ in range(profile.agent_count):
            participant = _participant(
                simulation=simulation,
                sequence_number=sequence_number,
                participant_type="background",
                profile_index=profile_index,
                strategy=profile,
                min_order_volume=simulation.background_min_order_volume,
                max_order_volume=simulation.background_max_order_volume,
            )
            participant.balances = _balances(simulation, participant_type="background")
            participants.append(participant)
            sequence_number += 1

    participant = _participant(
        simulation=simulation,
        sequence_number=sequence_number,
        participant_type="test",
        profile_index=None,
        strategy=simulation.test_strategy,
        min_order_volume=simulation.test_min_order_volume,
        max_order_volume=simulation.test_max_order_volume,
    )
    participant.balances = _balances(simulation, participant_type="test")
    participants.append(participant)
    return participants


def _participant(
    simulation: Simulation,
    sequence_number: int,
    participant_type: str,
    profile_index: int | None,
    strategy: BackgroundStrategyProfile | TestStrategy,
    min_order_volume: Decimal,
    max_order_volume: Decimal,
) -> SimulationParticipant:
    return SimulationParticipant(
        sequence_number=sequence_number,
        participant_type=participant_type,
        profile_index=profile_index,
        strategy_type=strategy.strategy_type,
        strategy_parameters=_strategy_parameters(strategy),
        rng_seed=_participant_seed(simulation.seed, sequence_number),
        min_order_volume=min_order_volume,
        max_order_volume=max_order_volume,
    )


def _participant_seed(experiment_seed: int, sequence_number: int) -> int:
    value = f"{experiment_seed}:{sequence_number}".encode("utf-8")
    digest = hashlib.sha256(value).digest()
    return int.from_bytes(digest[:8], "big") & ((1 << 63) - 1)


def _strategy_parameters(
    strategy: BackgroundStrategyProfile | TestStrategy,
) -> dict[str, object]:
    return {
        "buy_probability": _json_number(strategy.buy_probability),
        "sell_probability": _json_number(strategy.sell_probability),
        "hold_probability": _json_number(strategy.hold_probability),
        "price_deviation_pct": _json_number(strategy.price_deviation_pct),
        "trend_window": strategy.trend_window,
        "trend_threshold_pct": _json_number(strategy.trend_threshold_pct),
    }


def _json_number(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def _balances(
    simulation: Simulation,
    participant_type: str,
) -> list[ParticipantBalance]:
    first_instrument = simulation.instrument_configs[0].instrument
    quote_balance = (
        simulation.background_initial_quote_balance
        if participant_type == "background"
        else simulation.test_initial_quote_balance
    )
    amounts: dict[int, Decimal] = {
        first_instrument.quote_asset_id: quote_balance,
    }

    for config in simulation.instrument_configs:
        amount = (
            config.background_initial_base_balance
            if participant_type == "background"
            else config.test_initial_base_balance
        )
        amounts[config.instrument.base_asset_id] = amount

    return [
        ParticipantBalance(
            asset_id=asset_id,
            available=amount,
            reserved=Decimal("0"),
        )
        for asset_id, amount in amounts.items()
    ]
