import unittest
from decimal import Decimal
from random import Random

from backend.app.engine.strategies import (
    InvalidStrategyParametersError,
    decide,
)


RANDOM_PARAMETERS = {
    "buy_probability": 34,
    "sell_probability": 33,
    "hold_probability": 33,
    "price_deviation_pct": 1,
}

TREND_PARAMETERS = {
    "trend_window": 2,
    "trend_threshold_pct": 5,
}


class StrategyTests(unittest.TestCase):
    def test_random_strategy_is_reproducible_for_same_seed(self) -> None:
        first = decide(
            "random",
            RANDOM_PARAMETERS,
            [Decimal("100")],
            Decimal("1"),
            Decimal("5"),
            Random(42),
        )
        second = decide(
            "random",
            RANDOM_PARAMETERS,
            [Decimal("100")],
            Decimal("1"),
            Decimal("5"),
            Random(42),
        )

        self.assertEqual(first, second)

    def test_random_strategy_respects_price_and_volume_ranges(self) -> None:
        decision = decide(
            "random",
            {
                "buy_probability": 100,
                "sell_probability": 0,
                "hold_probability": 0,
                "price_deviation_pct": 2,
            },
            [Decimal("100")],
            Decimal("1"),
            Decimal("5"),
            Random(7),
        )

        self.assertEqual(decision.action, "BUY")
        self.assertIsNotNone(decision.price)
        self.assertIsNotNone(decision.volume)
        self.assertGreaterEqual(decision.price, Decimal("98"))
        self.assertLessEqual(decision.price, Decimal("102"))
        self.assertGreaterEqual(decision.volume, Decimal("1"))
        self.assertLessEqual(decision.volume, Decimal("5"))

    def test_random_strategy_can_hold(self) -> None:
        decision = decide(
            "random",
            {
                "buy_probability": 0,
                "sell_probability": 0,
                "hold_probability": 100,
                "price_deviation_pct": 1,
            },
            [Decimal("100")],
            Decimal("1"),
            Decimal("5"),
            Random(1),
        )

        self.assertEqual(decision.action, "HOLD")
        self.assertIsNone(decision.price)
        self.assertIsNone(decision.volume)

    def test_trend_strategy_holds_without_enough_history(self) -> None:
        decision = decide(
            "trend_following",
            TREND_PARAMETERS,
            [Decimal("100"), Decimal("104")],
            Decimal("1"),
            Decimal("5"),
            Random(1),
        )

        self.assertEqual(decision.action, "HOLD")

    def test_trend_strategy_buys_after_required_growth(self) -> None:
        decision = decide(
            "trend_following",
            TREND_PARAMETERS,
            [Decimal("100"), Decimal("102"), Decimal("106")],
            Decimal("1"),
            Decimal("5"),
            Random(1),
        )

        self.assertEqual(decision.action, "BUY")
        self.assertEqual(decision.price, Decimal("106.00000000"))

    def test_trend_strategy_sells_after_required_fall(self) -> None:
        decision = decide(
            "trend_following",
            TREND_PARAMETERS,
            [Decimal("100"), Decimal("98"), Decimal("94")],
            Decimal("1"),
            Decimal("5"),
            Random(1),
        )

        self.assertEqual(decision.action, "SELL")
        self.assertEqual(decision.price, Decimal("94.00000000"))

    def test_invalid_probability_sum_is_rejected(self) -> None:
        with self.assertRaises(InvalidStrategyParametersError):
            decide(
                "random",
                {
                    "buy_probability": 50,
                    "sell_probability": 30,
                    "hold_probability": 10,
                    "price_deviation_pct": 1,
                },
                [Decimal("100")],
                Decimal("1"),
                Decimal("5"),
                Random(1),
            )


if __name__ == "__main__":
    unittest.main()
