from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("run_id", "sequence_number", name="uq_orders_run_sequence"),
        CheckConstraint("side IN ('BUY', 'SELL')", name="ck_orders_side"),
        CheckConstraint(
            "status IN ('open', 'partial', 'filled', 'cancelled', 'rejected')",
            name="ck_orders_status",
        ),
        CheckConstraint(
            "price > 0 AND volume > 0 AND remaining_volume >= 0 "
            "AND remaining_volume <= volume AND reserved_amount >= 0",
            name="ck_orders_amounts",
        ),
        CheckConstraint("step >= 0 AND sequence_number > 0", name="ck_orders_event"),
        Index("ix_orders_book", "run_id", "instrument_id", "side", "status", "price"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("simulation_runs.id", ondelete="CASCADE"))
    participant_id: Mapped[int] = mapped_column(ForeignKey("simulation_participants.id", ondelete="CASCADE"))
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id", ondelete="RESTRICT"))
    sequence_number: Mapped[int] = mapped_column(Integer)
    step: Mapped[int] = mapped_column(Integer)
    side: Mapped[str] = mapped_column(String(4))
    status: Mapped[str] = mapped_column(String(16))
    price: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    volume: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    remaining_volume: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    reserved_amount: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    rejection_reason: Mapped[str | None] = mapped_column(String(200))


class Trade(Base):
    __tablename__ = "trades"
    __table_args__ = (
        UniqueConstraint("run_id", "sequence_number", name="uq_trades_run_sequence"),
        CheckConstraint("price > 0 AND volume > 0 AND quote_amount >= 0", name="ck_trades_amounts"),
        CheckConstraint("buy_order_id <> sell_order_id", name="ck_trades_distinct_orders"),
        CheckConstraint("step >= 0 AND sequence_number > 0", name="ck_trades_event"),
        Index("ix_trades_history", "run_id", "instrument_id", "sequence_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("simulation_runs.id", ondelete="CASCADE"))
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id", ondelete="RESTRICT"))
    buy_order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    sell_order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    sequence_number: Mapped[int] = mapped_column(Integer)
    step: Mapped[int] = mapped_column(Integer)
    price: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    volume: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    quote_amount: Mapped[Decimal] = mapped_column(Numeric(24, 8))
