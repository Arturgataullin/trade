"""One atomic model step; scheduling and wall-clock time never enter decisions."""

import json
import logging
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
from random import Random
from threading import Event, Thread

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.engine.strategies import StrategyDecision, decide
from backend.app.models.simulation_run import (
    SimulationParticipant, SimulationRun, SimulationRunInstrument,
)
from backend.app.models.trading import Order, Trade
from backend.app.services.trading import ACTIVE_STATUSES, cancel_order, lock_run, place_order


logger = logging.getLogger(__name__)


def finish_run(db: Session, run: SimulationRun, status: str) -> None:
    """Called with the run row locked; the caller owns the transaction."""
    order_ids = list(db.scalars(select(Order.id).where(
        Order.run_id == run.id, Order.status.in_(ACTIVE_STATUSES)
    ).order_by(Order.sequence_number)))
    for order_id in order_ids:
        cancel_order(db, run.id, order_id)
    run.status = status
    run.finished_at = datetime.now(timezone.utc)
    db.flush()


def execute_step(db: Session, run_id: int) -> bool:
    """Return True when a step was processed. Commit/rollback is caller-owned."""
    run = lock_run(db, run_id)
    if run.status != "running":
        return False
    if run.engine_version != "2":
        raise ValueError("Run uses an unsupported engine version; start a new run")
    if run.stop_requested:
        finish_run(db, run, "stopped")
        return False
    if run.current_step >= run.total_steps:
        finish_run(db, run, "completed")
        return False

    participants = list(db.scalars(select(SimulationParticipant).where(
        SimulationParticipant.run_id == run_id
    ).order_by(SimulationParticipant.sequence_number)))
    markets = list(db.scalars(select(SimulationRunInstrument).where(
        SimulationRunInstrument.run_id == run_id
    ).order_by(SimulationRunInstrument.instrument_id)))
    if not participants or not markets:
        raise ValueError("Run has no participants or instruments")

    # Only executed prices count toward a Trend Following window.
    window = max(
        (int(p.strategy_parameters.get("trend_window") or 0)
         for p in participants if p.strategy_type == "trend_following"),
        default=0,
    )
    history_limit = max(window + 1, 1)
    histories = {}
    last_sequences = {}
    for market in markets:
        recent = list(db.execute(select(Trade.sequence_number, Trade.price).where(
            Trade.run_id == run_id, Trade.instrument_id == market.instrument_id
        ).order_by(Trade.sequence_number.desc()).limit(history_limit)))
        histories[market.instrument_id] = [row.price for row in reversed(recent)]
        last_sequences[market.instrument_id] = recent[0].sequence_number if recent else 0

    step = run.current_step + 1
    for participant in participants:
        rng = Random(participant.rng_seed)
        if participant.rng_state is not None:
            version, internal, gaussian = participant.rng_state
            rng.setstate((version, tuple(internal), gaussian))
        for market in markets:
            history = histories[market.instrument_id]
            if participant.strategy_type == "trend_following" and not history:
                decision = StrategyDecision("HOLD")
            else:
                decision = decide(
                    participant.strategy_type,
                    participant.strategy_parameters,
                    history or [market.initial_price],
                    participant.min_order_volume,
                    participant.max_order_volume,
                    rng,
                )
            if decision.action == "HOLD":
                continue
            # Values below the quote precision cannot form a payable order.
            if (decision.price * decision.volume).quantize(
                Decimal("0.00000001"), rounding=ROUND_DOWN
            ) == 0:
                continue
            place_order(
                db, run_id, participant.id, market.instrument_id,
                decision.action, decision.price, decision.volume, step,
            )
            latest = list(db.execute(select(Trade.sequence_number, Trade.price).where(
                Trade.run_id == run_id,
                Trade.instrument_id == market.instrument_id,
                Trade.sequence_number > last_sequences[market.instrument_id],
            ).order_by(Trade.sequence_number)))
            if latest:
                history.extend(row.price for row in latest)
                del history[:-history_limit]
                last_sequences[market.instrument_id] = latest[-1].sequence_number
        participant.rng_state = json.loads(json.dumps(rng.getstate()))
        db.flush()

    run.current_step = step
    db.flush()
    if step == run.total_steps:
        finish_run(db, run, "completed")
    return True


def process_next_run(session_factory) -> bool:
    """SKIP LOCKED allows several processes to work on different runs safely."""
    with session_factory() as db:
        with db.begin():
            run = db.scalar(select(SimulationRun).where(
                SimulationRun.status == "running"
            ).order_by(SimulationRun.current_step, SimulationRun.id)
              .with_for_update(skip_locked=True).limit(1))
            if run is None:
                return False
            # A savepoint rolls back an entire failed step, including its RNG state.
            try:
                with db.begin_nested():
                    execute_step(db, run.id)
            except Exception:
                logger.exception("Simulation run %s failed", run.id)
                run = lock_run(db, run.id)
                finish_run(db, run, "failed")
                run.error_message = "Ошибка выполнения моделирования. Подробности в журнале сервера."
    return True


class SimulationWorker:
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.shutdown = Event()
        self.thread = Thread(target=self._loop, name="simulation-worker", daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self.shutdown.set()
        self.thread.join()

    def _loop(self):
        while not self.shutdown.is_set():
            try:
                processed = process_next_run(self.session_factory)
            except Exception:
                logger.exception("Simulation worker database operation failed")
                self.shutdown.wait(2)
                continue
            if not processed:
                self.shutdown.wait(0.2)
