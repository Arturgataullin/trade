from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, UniqueConstraint, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base

if TYPE_CHECKING:
    from backend.app.models.asset import Asset


class Instrument(Base):
    __tablename__ = "instruments"
    __table_args__ = (
        CheckConstraint(
            "base_asset_id <> quote_asset_id",
            name="ck_instruments_different_assets",
        ),
        UniqueConstraint(
            "base_asset_id",
            "quote_asset_id",
            name="uq_instruments_asset_pair",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    base_asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    quote_asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=true(),
        nullable=False,
    )

    base_asset: Mapped[Asset] = relationship(
        back_populates="base_instruments",
        foreign_keys=[base_asset_id],
    )
    quote_asset: Mapped[Asset] = relationship(
        back_populates="quote_instruments",
        foreign_keys=[quote_asset_id],
    )
