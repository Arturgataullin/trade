"""add assets and instruments

Revision ID: f3a91c7d2e4b
Revises: b7d4c0a9f2e1
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f3a91c7d2e4b"
down_revision: Union[str, Sequence[str], None] = "b7d4c0a9f2e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_assets_symbol"),
        "assets",
        ["symbol"],
        unique=True,
    )

    op.create_table(
        "instruments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("base_asset_id", sa.Integer(), nullable=False),
        sa.Column("quote_asset_id", sa.Integer(), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "base_asset_id <> quote_asset_id",
            name="ck_instruments_different_assets",
        ),
        sa.ForeignKeyConstraint(
            ["base_asset_id"],
            ["assets.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["quote_asset_id"],
            ["assets.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "base_asset_id",
            "quote_asset_id",
            name="uq_instruments_asset_pair",
        ),
    )


def downgrade() -> None:
    op.drop_table("instruments")
    op.drop_index(op.f("ix_assets_symbol"), table_name="assets")
    op.drop_table("assets")
