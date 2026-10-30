from dataclasses import dataclass
from decimal import Decimal
from random import Random
from typing import Mapping

from backend.app.engine.strategies import (
    StrategyDecision,
    StrategyType,
    decide,
)


@dataclass(frozen=True)
class ParticipantStrategyState:
    participant_id: int
    sequence_number: int
    strategy_type: StrategyType
    strategy_parameters: Mapping[str, object]
    min_order_volume: Decimal
    max_order_volume: Decimal
    rng_seed: int


@dataclass(frozen=True)
class InstrumentMarketState:
    instrument_id: int
    price_history: tuple[Decimal, ...]


@dataclass(frozen=True)
class DecisionEvent:
    step: int
    sequence_number: int
    participant_id: int
    instrument_id: int
    decision: StrategyDecision


def create_participant_generators(
    participants: list[ParticipantStrategyState],
) -> dict[int, Random]:
    return {
        participant.participant_id: Random(participant.rng_seed)
        for participant in participants
    }


def generate_step_decisions(
    step: int,
    participants: list[ParticipantStrategyState],
    instruments: list[InstrumentMarketState],
    generators: dict[int, Random],
) -> list[DecisionEvent]:
    if step <= 0:
        raise ValueError("Simulation step must be positive")

    events: list[DecisionEvent] = []
    event_sequence = 1
    ordered_participants = sorted(
        participants,
        key=lambda participant: participant.sequence_number,
    )
    ordered_instruments = sorted(
        instruments,
        key=lambda instrument: instrument.instrument_id,
    )

    for participant in ordered_participants:
        try:
            rng = generators[participant.participant_id]
        except KeyError as exc:
            raise ValueError(
                f"Missing random generator for participant "
                f"{participant.participant_id}"
            ) from exc

        for instrument in ordered_instruments:
            decision = decide(
                strategy_type=participant.strategy_type,
                parameters=participant.strategy_parameters,
                price_history=list(instrument.price_history),
                min_order_volume=participant.min_order_volume,
                max_order_volume=participant.max_order_volume,
                rng=rng,
            )
            events.append(
                DecisionEvent(
                    step=step,
                    sequence_number=event_sequence,
                    participant_id=participant.participant_id,
                    instrument_id=instrument.instrument_id,
                    decision=decision,
                )
            )
            event_sequence += 1

    return events
