from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base

if TYPE_CHECKING:
    from backend.app.models.instrument import Instrument


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True)

    symbol: Mapped[str] = mapped_column(
        String(16),
        unique=True,
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=true(),
        nullable=False,
    )

    base_instruments: Mapped[list[Instrument]] = relationship(
        back_populates="base_asset",
        foreign_keys="Instrument.base_asset_id",
    )
    quote_instruments: Mapped[list[Instrument]] = relationship(
        back_populates="quote_asset",
        foreign_keys="Instrument.quote_asset_id",
    )
