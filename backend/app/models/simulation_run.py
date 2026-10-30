from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    false,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base

if TYPE_CHECKING:
    from backend.app.models.asset import Asset
    from backend.app.models.instrument import Instrument
    from backend.app.models.simulation import Simulation


class SimulationRun(Base):
    __tablename__ = "simulation_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'stopped', 'completed', 'failed')",
            name="ck_simulation_runs_status",
        ),
        CheckConstraint(
            "current_step >= 0 AND total_steps > 0 AND current_step <= total_steps",
            name="ck_simulation_runs_steps",
        ),
        Index(
            "uq_simulation_runs_one_running",
            "simulation_id",
            unique=True,
            postgresql_where=text("status = 'running'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    simulation_id: Mapped[int] = mapped_column(
        ForeignKey("simulations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(16),
        default="running",
        server_default="running",
        nullable=False,
    )
    current_step: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )
    total_steps: Mapped[int] = mapped_column(Integer, nullable=False)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    engine_version: Mapped[str] = mapped_column(String(32), nullable=False)
    configuration_snapshot: Mapped[dict[str, object]] = mapped_column(
        JSON,
        nullable=False,
    )
    stop_requested: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=false(),
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(String(300))

    simulation: Mapped[Simulation] = relationship()
    instruments: Mapped[list[SimulationRunInstrument]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="SimulationRunInstrument.id",
    )
    participants: Mapped[list[SimulationParticipant]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="SimulationParticipant.sequence_number",
    )


class SimulationRunInstrument(Base):
    __tablename__ = "simulation_run_instruments"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "instrument_id",
            name="uq_simulation_run_instruments_pair",
        ),
        CheckConstraint(
            "initial_price > 0 AND last_price > 0",
            name="ck_simulation_run_instruments_prices",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("simulation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    initial_price: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    last_price: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)

    run: Mapped[SimulationRun] = relationship(back_populates="instruments")
    instrument: Mapped[Instrument] = relationship()


class SimulationParticipant(Base):
    __tablename__ = "simulation_participants"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "sequence_number",
            name="uq_simulation_participants_sequence",
        ),
        CheckConstraint(
            "participant_type IN ('background', 'test')",
            name="ck_simulation_participants_type",
        ),
        CheckConstraint(
            "strategy_type IN ('random', 'trend_following')",
            name="ck_simulation_participants_strategy_type",
        ),
        CheckConstraint(
            "min_order_volume > 0 AND max_order_volume >= min_order_volume",
            name="ck_simulation_participants_volume_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("simulation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    participant_type: Mapped[str] = mapped_column(String(16), nullable=False)
    profile_index: Mapped[int | None] = mapped_column(Integer)
    strategy_type: Mapped[str] = mapped_column(String(32), nullable=False)
    strategy_parameters: Mapped[dict[str, object]] = mapped_column(
        JSON,
        nullable=False,
    )
    rng_seed: Mapped[int] = mapped_column(BigInteger, nullable=False)
    rng_state: Mapped[list | None] = mapped_column(JSON)
    min_order_volume: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    max_order_volume: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)

    run: Mapped[SimulationRun] = relationship(back_populates="participants")
    balances: Mapped[list[ParticipantBalance]] = relationship(
        back_populates="participant",
        cascade="all, delete-orphan",
        order_by="ParticipantBalance.asset_id",
    )


class ParticipantBalance(Base):
    __tablename__ = "participant_balances"
    __table_args__ = (
        UniqueConstraint(
            "participant_id",
            "asset_id",
            name="uq_participant_balances_asset",
        ),
        CheckConstraint(
            "available >= 0 AND reserved >= 0",
            name="ck_participant_balances_non_negative",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    participant_id: Mapped[int] = mapped_column(
        ForeignKey("simulation_participants.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    available: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    reserved: Mapped[Decimal] = mapped_column(
        Numeric(24, 8),
        default=Decimal("0"),
        server_default="0",
        nullable=False,
    )

    participant: Mapped[SimulationParticipant] = relationship(
        back_populates="balances"
    )
    asset: Mapped[Asset] = relationship()
