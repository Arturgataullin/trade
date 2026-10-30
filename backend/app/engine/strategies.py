from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from random import Random
from typing import Literal, Mapping


Action = Literal["BUY", "SELL", "HOLD"]
StrategyType = Literal["random", "trend_following"]

MONEY_QUANTUM = Decimal("0.00000001")
PERCENT = Decimal("100")


class InvalidStrategyParametersError(ValueError):
    """Raised when persisted strategy parameters are incomplete or invalid."""


@dataclass(frozen=True)
class StrategyDecision:
    action: Action
    price: Decimal | None = None
    volume: Decimal | None = None


def decide(
    strategy_type: StrategyType,
    parameters: Mapping[str, object],
    price_history: list[Decimal],
    min_order_volume: Decimal,
    max_order_volume: Decimal,
    rng: Random,
) -> StrategyDecision:
    _validate_common_inputs(
        price_history,
        min_order_volume,
        max_order_volume,
    )

    if strategy_type == "random":
        return random_decision(
            parameters,
            price_history[-1],
            min_order_volume,
            max_order_volume,
            rng,
        )
    if strategy_type == "trend_following":
        return trend_following_decision(
            parameters,
            price_history,
            min_order_volume,
            max_order_volume,
            rng,
        )
    raise InvalidStrategyParametersError(
        f"Unsupported strategy type: {strategy_type}"
    )


def random_decision(
    parameters: Mapping[str, object],
    last_price: Decimal,
    min_order_volume: Decimal,
    max_order_volume: Decimal,
    rng: Random,
) -> StrategyDecision:
    buy_probability = _required_decimal(parameters, "buy_probability")
    sell_probability = _required_decimal(parameters, "sell_probability")
    hold_probability = _required_decimal(parameters, "hold_probability")
    price_deviation_pct = _required_decimal(parameters, "price_deviation_pct")

    probabilities = (buy_probability, sell_probability, hold_probability)
    if any(value < 0 for value in probabilities):
        raise InvalidStrategyParametersError("Probabilities must be non-negative")
    if abs(sum(probabilities) - PERCENT) > Decimal("0.001"):
        raise InvalidStrategyParametersError("Probabilities must sum to 100")
    if price_deviation_pct < 0:
        raise InvalidStrategyParametersError(
            "Price deviation must be non-negative"
        )

    roll = _random_decimal(rng) * PERCENT
    if roll < buy_probability:
        action: Action = "BUY"
    elif roll < buy_probability + sell_probability:
        action = "SELL"
    else:
        return StrategyDecision(action="HOLD")

    direction = _random_decimal(rng) * 2 - 1
    price_multiplier = Decimal("1") + (
        direction * price_deviation_pct / PERCENT
    )
    price = max(
        MONEY_QUANTUM,
        _quantize(last_price * price_multiplier),
    )
    volume = _random_volume(min_order_volume, max_order_volume, rng)
    return StrategyDecision(action=action, price=price, volume=volume)


def trend_following_decision(
    parameters: Mapping[str, object],
    price_history: list[Decimal],
    min_order_volume: Decimal,
    max_order_volume: Decimal,
    rng: Random,
) -> StrategyDecision:
    trend_window = _required_int(parameters, "trend_window")
    threshold_pct = _required_decimal(parameters, "trend_threshold_pct")
    if trend_window <= 0:
        raise InvalidStrategyParametersError("Trend window must be positive")
    if threshold_pct <= 0:
        raise InvalidStrategyParametersError("Trend threshold must be positive")

    if len(price_history) <= trend_window:
        return StrategyDecision(action="HOLD")

    current_price = price_history[-1]
    reference_price = price_history[-1 - trend_window]
    if reference_price <= 0:
        raise InvalidStrategyParametersError("Reference price must be positive")

    change_pct = (current_price - reference_price) / reference_price * PERCENT
    if change_pct >= threshold_pct:
        action: Action = "BUY"
    elif change_pct <= -threshold_pct:
        action = "SELL"
    else:
        return StrategyDecision(action="HOLD")

    return StrategyDecision(
        action=action,
        price=_quantize(current_price),
        volume=_random_volume(min_order_volume, max_order_volume, rng),
    )


def _validate_common_inputs(
    price_history: list[Decimal],
    min_order_volume: Decimal,
    max_order_volume: Decimal,
) -> None:
    if not price_history:
        raise InvalidStrategyParametersError("Price history must not be empty")
    if price_history[-1] <= 0:
        raise InvalidStrategyParametersError("Last price must be positive")
    if min_order_volume <= 0 or max_order_volume < min_order_volume:
        raise InvalidStrategyParametersError("Invalid order volume range")


def _required_decimal(
    parameters: Mapping[str, object],
    name: str,
) -> Decimal:
    value = parameters.get(name)
    if value is None:
        raise InvalidStrategyParametersError(f"Missing strategy parameter: {name}")
    try:
        return Decimal(str(value))
    except Exception as exc:
        raise InvalidStrategyParametersError(
            f"Invalid strategy parameter: {name}"
        ) from exc


def _required_int(parameters: Mapping[str, object], name: str) -> int:
    value = parameters.get(name)
    if value is None or isinstance(value, bool):
        raise InvalidStrategyParametersError(f"Missing strategy parameter: {name}")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise InvalidStrategyParametersError(
            f"Invalid strategy parameter: {name}"
        ) from exc
    if Decimal(str(value)) != Decimal(result):
        raise InvalidStrategyParametersError(
            f"Invalid strategy parameter: {name}"
        )
    return result


def _random_volume(
    minimum: Decimal,
    maximum: Decimal,
    rng: Random,
) -> Decimal:
    if minimum == maximum:
        return _quantize(minimum)
    return _quantize(minimum + (maximum - minimum) * _random_decimal(rng))


def _random_decimal(rng: Random) -> Decimal:
    return Decimal(str(rng.random()))


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
