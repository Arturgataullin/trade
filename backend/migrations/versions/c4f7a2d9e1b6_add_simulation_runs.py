"""add simulation runs

Revision ID: c4f7a2d9e1b6
Revises: 8c2d4e6f1a3b
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4f7a2d9e1b6"
down_revision: Union[str, Sequence[str], None] = "8c2d4e6f1a3b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "simulation_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("simulation_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default="running",
            nullable=False,
        ),
        sa.Column(
            "current_step",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("total_steps", sa.Integer(), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("engine_version", sa.String(length=32), nullable=False),
        sa.Column("configuration_snapshot", sa.JSON(), nullable=False),
        sa.Column(
            "stop_requested",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('running', 'stopped', 'completed', 'failed')",
            name="ck_simulation_runs_status",
        ),
        sa.CheckConstraint(
            "current_step >= 0 AND total_steps > 0 "
            "AND current_step <= total_steps",
            name="ck_simulation_runs_steps",
        ),
        sa.ForeignKeyConstraint(
            ["simulation_id"],
            ["simulations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_simulation_runs_simulation_id"),
        "simulation_runs",
        ["simulation_id"],
        unique=False,
    )
    op.create_index(
        "uq_simulation_runs_one_running",
        "simulation_runs",
        ["simulation_id"],
        unique=True,
        postgresql_where=sa.text("status = 'running'"),
    )

    op.create_table(
        "simulation_run_instruments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("initial_price", sa.Numeric(precision=24, scale=8), nullable=False),
        sa.Column("last_price", sa.Numeric(precision=24, scale=8), nullable=False),
        sa.CheckConstraint(
            "initial_price > 0 AND last_price > 0",
            name="ck_simulation_run_instruments_prices",
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["simulation_runs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "instrument_id",
            name="uq_simulation_run_instruments_pair",
        ),
    )

    op.create_table(
        "simulation_participants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("participant_type", sa.String(length=16), nullable=False),
        sa.Column("profile_index", sa.Integer()),
        sa.Column("strategy_type", sa.String(length=32), nullable=False),
        sa.Column("strategy_parameters", sa.JSON(), nullable=False),
        sa.Column("rng_seed", sa.BigInteger(), nullable=False),
        sa.Column(
            "min_order_volume",
            sa.Numeric(precision=24, scale=8),
            nullable=False,
        ),
        sa.Column(
            "max_order_volume",
            sa.Numeric(precision=24, scale=8),
            nullable=False,
        ),
        sa.CheckConstraint(
            "participant_type IN ('background', 'test')",
            name="ck_simulation_participants_type",
        ),
        sa.CheckConstraint(
            "strategy_type IN ('random', 'trend_following')",
            name="ck_simulation_participants_strategy_type",
        ),
        sa.CheckConstraint(
            "min_order_volume > 0 AND max_order_volume >= min_order_volume",
            name="ck_simulation_participants_volume_range",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["simulation_runs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "sequence_number",
            name="uq_simulation_participants_sequence",
        ),
    )

    op.create_table(
        "participant_balances",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("participant_id", sa.Integer(), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("available", sa.Numeric(precision=24, scale=8), nullable=False),
        sa.Column(
            "reserved",
            sa.Numeric(precision=24, scale=8),
            server_default="0",
            nullable=False,
        ),
        sa.CheckConstraint(
            "available >= 0 AND reserved >= 0",
            name="ck_participant_balances_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["assets.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["participant_id"],
            ["simulation_participants.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "participant_id",
            "asset_id",
            name="uq_participant_balances_asset",
        ),
    )


def downgrade() -> None:
    op.drop_table("participant_balances")
    op.drop_table("simulation_participants")
    op.drop_table("simulation_run_instruments")
    op.drop_index(
        "uq_simulation_runs_one_running",
        table_name="simulation_runs",
        postgresql_where=sa.text("status = 'running'"),
    )
    op.drop_index(
        op.f("ix_simulation_runs_simulation_id"),
        table_name="simulation_runs",
    )
    op.drop_table("simulation_runs")
