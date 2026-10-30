"""add orders and trades

Revision ID: e9b5a7c3d210
Revises: c4f7a2d9e1b6
"""

from alembic import op
import sqlalchemy as sa


revision = "e9b5a7c3d210"
down_revision = "c4f7a2d9e1b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("simulation_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("participant_id", sa.Integer(), sa.ForeignKey("simulation_participants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("instrument_id", sa.Integer(), sa.ForeignKey("instruments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("step", sa.Integer(), nullable=False),
        sa.Column("side", sa.String(4), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("price", sa.Numeric(24, 8), nullable=False),
        sa.Column("volume", sa.Numeric(24, 8), nullable=False),
        sa.Column("remaining_volume", sa.Numeric(24, 8), nullable=False),
        sa.Column("reserved_amount", sa.Numeric(24, 8), nullable=False),
        sa.Column("rejection_reason", sa.String(200)),
        sa.UniqueConstraint("run_id", "sequence_number", name="uq_orders_run_sequence"),
        sa.CheckConstraint("side IN ('BUY', 'SELL')", name="ck_orders_side"),
        sa.CheckConstraint("status IN ('open', 'partial', 'filled', 'cancelled', 'rejected')", name="ck_orders_status"),
        sa.CheckConstraint("price > 0 AND volume > 0 AND remaining_volume >= 0 AND remaining_volume <= volume AND reserved_amount >= 0", name="ck_orders_amounts"),
        sa.CheckConstraint("step >= 0 AND sequence_number > 0", name="ck_orders_event"),
    )
    op.create_index("ix_orders_book", "orders", ["run_id", "instrument_id", "side", "status", "price"])
    op.create_table(
        "trades",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("simulation_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("instrument_id", sa.Integer(), sa.ForeignKey("instruments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("buy_order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sell_order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("step", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(24, 8), nullable=False),
        sa.Column("volume", sa.Numeric(24, 8), nullable=False),
        sa.Column("quote_amount", sa.Numeric(24, 8), nullable=False),
        sa.UniqueConstraint("run_id", "sequence_number", name="uq_trades_run_sequence"),
        sa.CheckConstraint("price > 0 AND volume > 0 AND quote_amount >= 0", name="ck_trades_amounts"),
        sa.CheckConstraint("buy_order_id <> sell_order_id", name="ck_trades_distinct_orders"),
        sa.CheckConstraint("step >= 0 AND sequence_number > 0", name="ck_trades_event"),
    )
    op.create_index("ix_trades_history", "trades", ["run_id", "instrument_id", "sequence_number"])


def downgrade() -> None:
    op.drop_index("ix_trades_history", table_name="trades")
    op.drop_table("trades")
    op.drop_index("ix_orders_book", table_name="orders")
    op.drop_table("orders")
