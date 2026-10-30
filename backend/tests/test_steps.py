import unittest
from decimal import Decimal

from backend.app.engine.steps import (
    InstrumentMarketState,
    ParticipantStrategyState,
    create_participant_generators,
    generate_step_decisions,
)


def random_participant(
    participant_id: int,
    sequence_number: int,
    rng_seed: int,
) -> ParticipantStrategyState:
    return ParticipantStrategyState(
        participant_id=participant_id,
        sequence_number=sequence_number,
        strategy_type="random",
        strategy_parameters={
            "buy_probability": 34,
            "sell_probability": 33,
            "hold_probability": 33,
            "price_deviation_pct": 1,
        },
        min_order_volume=Decimal("0.01"),
        max_order_volume=Decimal("1"),
        rng_seed=rng_seed,
    )


class SimulationStepTests(unittest.TestCase):
    def setUp(self) -> None:
        self.participants = [
            random_participant(20, 2, 200),
            random_participant(10, 1, 100),
        ]
        self.instruments = [
            InstrumentMarketState(2, (Decimal("200"),)),
            InstrumentMarketState(1, (Decimal("100"),)),
        ]

    def test_step_uses_stable_participant_and_instrument_order(self) -> None:
        events = generate_step_decisions(
            1,
            self.participants,
            self.instruments,
            create_participant_generators(self.participants),
        )

        self.assertEqual(
            [(event.participant_id, event.instrument_id) for event in events],
            [(10, 1), (10, 2), (20, 1), (20, 2)],
        )
        self.assertEqual(
            [event.sequence_number for event in events],
            [1, 2, 3, 4],
        )

    def test_replaying_with_same_seeds_produces_same_events(self) -> None:
        first = generate_step_decisions(
            1,
            self.participants,
            self.instruments,
            create_participant_generators(self.participants),
        )
        second = generate_step_decisions(
            1,
            self.participants,
            self.instruments,
            create_participant_generators(self.participants),
        )

        self.assertEqual(first, second)

    def test_generators_continue_their_stream_between_steps(self) -> None:
        generators = create_participant_generators(self.participants)
        first = generate_step_decisions(
            1,
            self.participants,
            self.instruments,
            generators,
        )
        second = generate_step_decisions(
            2,
            self.participants,
            self.instruments,
            generators,
        )

        self.assertNotEqual(
            [event.decision for event in first],
            [event.decision for event in second],
        )


if __name__ == "__main__":
    unittest.main()
