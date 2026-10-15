from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from backend.app.models.asset import Asset
from backend.app.models.instrument import Instrument
from backend.app.schemas.market import AssetWrite, InstrumentWrite


class AssetNotFoundError(Exception):
    """Raised when an asset does not exist."""


class InstrumentNotFoundError(Exception):
    """Raised when a trading instrument does not exist."""


class MarketConflictError(Exception):
    """Raised when a symbol or an asset pair already exists."""


class InvalidInstrumentError(Exception):
    """Raised when an instrument references an invalid asset pair."""


def list_assets(db: Session) -> list[Asset]:
    statement = select(Asset).order_by(Asset.symbol)
    return list(db.scalars(statement).all())


def get_asset(db: Session, asset_id: int) -> Asset:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise AssetNotFoundError
    return asset


def create_asset(db: Session, data: AssetWrite) -> Asset:
    asset = Asset(**data.model_dump())
    db.add(asset)
    return _commit_asset(db, asset)


def update_asset(db: Session, asset_id: int, data: AssetWrite) -> Asset:
    asset = get_asset(db, asset_id)
    for field, value in data.model_dump().items():
        setattr(asset, field, value)
    return _commit_asset(db, asset)


def _commit_asset(db: Session, asset: Asset) -> Asset:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise MarketConflictError from exc
    db.refresh(asset)
    return asset


def list_instruments(db: Session) -> list[Instrument]:
    statement = (
        select(Instrument)
        .options(
            selectinload(Instrument.base_asset),
            selectinload(Instrument.quote_asset),
        )
        .order_by(Instrument.id)
    )
    return list(db.scalars(statement).all())


def get_instrument(db: Session, instrument_id: int) -> Instrument:
    statement = (
        select(Instrument)
        .where(Instrument.id == instrument_id)
        .options(
            selectinload(Instrument.base_asset),
            selectinload(Instrument.quote_asset),
        )
    )
    instrument = db.scalar(statement)
    if instrument is None:
        raise InstrumentNotFoundError
    return instrument


def create_instrument(db: Session, data: InstrumentWrite) -> Instrument:
    _validate_asset_pair(db, data.base_asset_id, data.quote_asset_id)
    instrument = Instrument(**data.model_dump())
    db.add(instrument)
    return _commit_instrument(db, instrument)


def update_instrument(
    db: Session,
    instrument_id: int,
    data: InstrumentWrite,
) -> Instrument:
    instrument = get_instrument(db, instrument_id)
    _validate_asset_pair(db, data.base_asset_id, data.quote_asset_id)
    for field, value in data.model_dump().items():
        setattr(instrument, field, value)
    return _commit_instrument(db, instrument)


def _validate_asset_pair(
    db: Session,
    base_asset_id: int,
    quote_asset_id: int,
) -> None:
    if base_asset_id == quote_asset_id:
        raise InvalidInstrumentError("Base and quote assets must be different")

    assets = db.scalars(
        select(Asset).where(Asset.id.in_([base_asset_id, quote_asset_id]))
    ).all()
    if len(assets) != 2:
        raise InvalidInstrumentError("Base or quote asset does not exist")


def _commit_instrument(db: Session, instrument: Instrument) -> Instrument:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise MarketConflictError from exc

    return get_instrument(db, instrument.id)
