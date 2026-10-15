from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.app.schemas.market import InstrumentRead


StrategyType = Literal["random", "trend_following"]
NonNegativeNumber = Annotated[float, Field(ge=0)]
PositiveNumber = Annotated[float, Field(gt=0)]
Probability = Annotated[float, Field(ge=0, le=100)]


class StrategyParameters(BaseModel):
    strategy_type: StrategyType
    buy_probability: Probability | None = None
    sell_probability: Probability | None = None
    hold_probability: Probability | None = None
    price_deviation_pct: NonNegativeNumber | None = None
    trend_window: int | None = Field(default=None, gt=0)
    trend_threshold_pct: PositiveNumber | None = None

    @model_validator(mode="after")
    def validate_strategy_parameters(self) -> Self:
        if self.strategy_type == "random":
            probabilities = (
                self.buy_probability,
                self.sell_probability,
                self.hold_probability,
            )
            if any(value is None for value in probabilities):
                raise ValueError(
                    "Random strategy requires BUY, SELL and HOLD probabilities"
                )
            if self.price_deviation_pct is None:
                raise ValueError("Random strategy requires price deviation")
            if abs(sum(value for value in probabilities if value is not None) - 100) > 0.001:
                raise ValueError("Random strategy probabilities must sum to 100")
        else:
            if self.trend_window is None or self.trend_threshold_pct is None:
                raise ValueError(
                    "Trend Following requires a window and a threshold"
                )

        return self


class BackgroundStrategyProfileWrite(StrategyParameters):
    agent_count: int = Field(gt=0)


class BackgroundStrategyProfileRead(BackgroundStrategyProfileWrite):
    id: int

    model_config = ConfigDict(from_attributes=True)


class TestStrategyWrite(StrategyParameters):
    pass


class TestStrategyRead(TestStrategyWrite):
    id: int

    model_config = ConfigDict(from_attributes=True)


class SimulationInstrumentWrite(BaseModel):
    instrument_id: int = Field(gt=0)
    initial_price: PositiveNumber
    background_initial_base_balance: NonNegativeNumber
    test_initial_base_balance: NonNegativeNumber


class SimulationInstrumentRead(SimulationInstrumentWrite):
    id: int
    instrument: InstrumentRead

    model_config = ConfigDict(from_attributes=True)


class SimulationWrite(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    duration_steps: int = Field(gt=0)
    seed: int
    background_initial_quote_balance: NonNegativeNumber
    background_min_order_volume: PositiveNumber
    background_max_order_volume: PositiveNumber
    test_initial_quote_balance: NonNegativeNumber
    test_min_order_volume: PositiveNumber
    test_max_order_volume: PositiveNumber
    instrument_configs: list[SimulationInstrumentWrite] = Field(
        min_length=1,
        max_length=2,
    )
    background_profiles: list[BackgroundStrategyProfileWrite] = Field(
        min_length=1,
    )
    test_strategy: TestStrategyWrite

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Experiment name must not be empty")
        return normalized

    @model_validator(mode="after")
    def validate_configuration(self) -> Self:
        if self.background_min_order_volume > self.background_max_order_volume:
            raise ValueError(
                "Background minimum order volume must not exceed maximum"
            )
        if self.test_min_order_volume > self.test_max_order_volume:
            raise ValueError("Test minimum order volume must not exceed maximum")

        instrument_ids = [item.instrument_id for item in self.instrument_configs]
        if len(instrument_ids) != len(set(instrument_ids)):
            raise ValueError("Each trading instrument can only be selected once")

        return self


class SimulationRead(SimulationWrite):
    id: int
    owner_id: int
    created_at: datetime
    updated_at: datetime
    instrument_configs: list[SimulationInstrumentRead]
    background_profiles: list[BackgroundStrategyProfileRead]
    test_strategy: TestStrategyRead

    model_config = ConfigDict(from_attributes=True)
