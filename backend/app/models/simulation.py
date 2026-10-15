from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base

if TYPE_CHECKING:
    from backend.app.models.instrument import Instrument
    from backend.app.models.user import User


class Simulation(Base):
    __tablename__ = "simulations"
    __table_args__ = (
        CheckConstraint("duration_steps > 0", name="ck_simulations_duration_positive"),
        CheckConstraint(
            "background_initial_quote_balance >= 0",
            name="ck_simulations_background_quote_balance_non_negative",
        ),
        CheckConstraint(
            "background_min_order_volume > 0 AND "
            "background_max_order_volume >= background_min_order_volume",
            name="ck_simulations_background_volume_range",
        ),
        CheckConstraint(
            "test_initial_quote_balance >= 0",
            name="ck_simulations_test_quote_balance_non_negative",
        ),
        CheckConstraint(
            "test_min_order_volume > 0 AND "
            "test_max_order_volume >= test_min_order_volume",
            name="ck_simulations_test_volume_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    duration_steps: Mapped[int] = mapped_column(Integer, nullable=False)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    background_initial_quote_balance: Mapped[Decimal] = mapped_column(
        Numeric(24, 8),
        nullable=False,
    )
    background_min_order_volume: Mapped[Decimal] = mapped_column(
        Numeric(24, 8),
        nullable=False,
    )
    background_max_order_volume: Mapped[Decimal] = mapped_column(
        Numeric(24, 8),
        nullable=False,
    )
    test_initial_quote_balance: Mapped[Decimal] = mapped_column(
        Numeric(24, 8),
        nullable=False,
    )
    test_min_order_volume: Mapped[Decimal] = mapped_column(
        Numeric(24, 8),
        nullable=False,
    )
    test_max_order_volume: Mapped[Decimal] = mapped_column(
        Numeric(24, 8),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    owner: Mapped[User] = relationship()
    instrument_configs: Mapped[list[SimulationInstrument]] = relationship(
        back_populates="simulation",
        cascade="all, delete-orphan",
        order_by="SimulationInstrument.id",
    )
    background_profiles: Mapped[list[BackgroundStrategyProfile]] = relationship(
        back_populates="simulation",
        cascade="all, delete-orphan",
        order_by="BackgroundStrategyProfile.id",
    )
    test_strategy: Mapped[TestStrategy] = relationship(
        back_populates="simulation",
        cascade="all, delete-orphan",
        uselist=False,
    )


class SimulationInstrument(Base):
    __tablename__ = "simulation_instruments"
    __table_args__ = (
        UniqueConstraint(
            "simulation_id",
            "instrument_id",
            name="uq_simulation_instruments_pair",
        ),
        CheckConstraint(
            "initial_price > 0",
            name="ck_simulation_instruments_price_positive",
        ),
        CheckConstraint(
            "background_initial_base_balance >= 0",
            name="ck_simulation_instruments_background_balance_non_negative",
        ),
        CheckConstraint(
            "test_initial_base_balance >= 0",
            name="ck_simulation_instruments_test_balance_non_negative",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    simulation_id: Mapped[int] = mapped_column(
        ForeignKey("simulations.id", ondelete="CASCADE"),
        nullable=False,
    )
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    initial_price: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    background_initial_base_balance: Mapped[Decimal] = mapped_column(
        Numeric(24, 8),
        nullable=False,
    )
    test_initial_base_balance: Mapped[Decimal] = mapped_column(
        Numeric(24, 8),
        nullable=False,
    )

    simulation: Mapped[Simulation] = relationship(
        back_populates="instrument_configs",
    )
    instrument: Mapped[Instrument] = relationship()


class BackgroundStrategyProfile(Base):
    __tablename__ = "background_strategy_profiles"
    __table_args__ = (
        CheckConstraint(
            "strategy_type IN ('random', 'trend_following')",
            name="ck_background_profiles_strategy_type",
        ),
        CheckConstraint(
            "agent_count > 0",
            name="ck_background_profiles_agent_count_positive",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    simulation_id: Mapped[int] = mapped_column(
        ForeignKey("simulations.id", ondelete="CASCADE"),
        nullable=False,
    )
    strategy_type: Mapped[str] = mapped_column(String(32), nullable=False)
    agent_count: Mapped[int] = mapped_column(Integer, nullable=False)
    buy_probability: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))
    sell_probability: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))
    hold_probability: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))
    price_deviation_pct: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    trend_window: Mapped[int | None] = mapped_column(Integer)
    trend_threshold_pct: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))

    simulation: Mapped[Simulation] = relationship(
        back_populates="background_profiles",
    )


class TestStrategy(Base):
    __tablename__ = "test_strategies"
    __table_args__ = (
        CheckConstraint(
            "strategy_type IN ('random', 'trend_following')",
            name="ck_test_strategies_strategy_type",
        ),
        UniqueConstraint("simulation_id", name="uq_test_strategies_simulation_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    simulation_id: Mapped[int] = mapped_column(
        ForeignKey("simulations.id", ondelete="CASCADE"),
        nullable=False,
    )
    strategy_type: Mapped[str] = mapped_column(String(32), nullable=False)
    buy_probability: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))
    sell_probability: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))
    hold_probability: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))
    price_deviation_pct: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    trend_window: Mapped[int | None] = mapped_column(Integer)
    trend_threshold_pct: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))

    simulation: Mapped[Simulation] = relationship(back_populates="test_strategy")
