"""add simulation configurations

Revision ID: 8c2d4e6f1a3b
Revises: f3a91c7d2e4b
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8c2d4e6f1a3b"
down_revision: Union[str, Sequence[str], None] = "f3a91c7d2e4b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "simulations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("duration_steps", sa.Integer(), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column(
            "background_initial_quote_balance",
            sa.Numeric(precision=24, scale=8),
            nullable=False,
        ),
        sa.Column(
            "background_min_order_volume",
            sa.Numeric(precision=24, scale=8),
            nullable=False,
        ),
        sa.Column(
            "background_max_order_volume",
            sa.Numeric(precision=24, scale=8),
            nullable=False,
        ),
        sa.Column(
            "test_initial_quote_balance",
            sa.Numeric(precision=24, scale=8),
            nullable=False,
        ),
        sa.Column(
            "test_min_order_volume",
            sa.Numeric(precision=24, scale=8),
            nullable=False,
        ),
        sa.Column(
            "test_max_order_volume",
            sa.Numeric(precision=24, scale=8),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "background_initial_quote_balance >= 0",
            name="ck_simulations_background_quote_balance_non_negative",
        ),
        sa.CheckConstraint(
            "background_min_order_volume > 0 AND "
            "background_max_order_volume >= background_min_order_volume",
            name="ck_simulations_background_volume_range",
        ),
        sa.CheckConstraint(
            "duration_steps > 0",
            name="ck_simulations_duration_positive",
        ),
        sa.CheckConstraint(
            "test_initial_quote_balance >= 0",
            name="ck_simulations_test_quote_balance_non_negative",
        ),
        sa.CheckConstraint(
            "test_min_order_volume > 0 AND "
            "test_max_order_volume >= test_min_order_volume",
            name="ck_simulations_test_volume_range",
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_simulations_owner_id"),
        "simulations",
        ["owner_id"],
        unique=False,
    )

    op.create_table(
        "background_strategy_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("simulation_id", sa.Integer(), nullable=False),
        sa.Column("strategy_type", sa.String(length=32), nullable=False),
        sa.Column("agent_count", sa.Integer(), nullable=False),
        sa.Column("buy_probability", sa.Numeric(precision=7, scale=4)),
        sa.Column("sell_probability", sa.Numeric(precision=7, scale=4)),
        sa.Column("hold_probability", sa.Numeric(precision=7, scale=4)),
        sa.Column("price_deviation_pct", sa.Numeric(precision=12, scale=6)),
        sa.Column("trend_window", sa.Integer()),
        sa.Column("trend_threshold_pct", sa.Numeric(precision=12, scale=6)),
        sa.CheckConstraint(
            "agent_count > 0",
            name="ck_background_profiles_agent_count_positive",
        ),
        sa.CheckConstraint(
            "strategy_type IN ('random', 'trend_following')",
            name="ck_background_profiles_strategy_type",
        ),
        sa.ForeignKeyConstraint(
            ["simulation_id"],
            ["simulations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "simulation_instruments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("simulation_id", sa.Integer(), nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column(
            "initial_price",
            sa.Numeric(precision=24, scale=8),
            nullable=False,
        ),
        sa.Column(
            "background_initial_base_balance",
            sa.Numeric(precision=24, scale=8),
            nullable=False,
        ),
        sa.Column(
            "test_initial_base_balance",
            sa.Numeric(precision=24, scale=8),
            nullable=False,
        ),
        sa.CheckConstraint(
            "background_initial_base_balance >= 0",
            name="ck_simulation_instruments_background_balance_non_negative",
        ),
        sa.CheckConstraint(
            "initial_price > 0",
            name="ck_simulation_instruments_price_positive",
        ),
        sa.CheckConstraint(
            "test_initial_base_balance >= 0",
            name="ck_simulation_instruments_test_balance_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["simulation_id"],
            ["simulations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "simulation_id",
            "instrument_id",
            name="uq_simulation_instruments_pair",
        ),
    )

    op.create_table(
        "test_strategies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("simulation_id", sa.Integer(), nullable=False),
        sa.Column("strategy_type", sa.String(length=32), nullable=False),
        sa.Column("buy_probability", sa.Numeric(precision=7, scale=4)),
        sa.Column("sell_probability", sa.Numeric(precision=7, scale=4)),
        sa.Column("hold_probability", sa.Numeric(precision=7, scale=4)),
        sa.Column("price_deviation_pct", sa.Numeric(precision=12, scale=6)),
        sa.Column("trend_window", sa.Integer()),
        sa.Column("trend_threshold_pct", sa.Numeric(precision=12, scale=6)),
        sa.CheckConstraint(
            "strategy_type IN ('random', 'trend_following')",
            name="ck_test_strategies_strategy_type",
        ),
        sa.ForeignKeyConstraint(
            ["simulation_id"],
            ["simulations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "simulation_id",
            name="uq_test_strategies_simulation_id",
        ),
    )


def downgrade() -> None:
    op.drop_table("test_strategies")
    op.drop_table("simulation_instruments")
    op.drop_table("background_strategy_profiles")
    op.drop_index(op.f("ix_simulations_owner_id"), table_name="simulations")
    op.drop_table("simulations")
