from fastapi import APIRouter, HTTPException, status

from backend.app.api.dependencies import AdminUser, DbSession
from backend.app.schemas.market import (
    AssetRead,
    AssetWrite,
    InstrumentRead,
    InstrumentWrite,
)
from backend.app.services.market import (
    AssetNotFoundError,
    InstrumentNotFoundError,
    InvalidInstrumentError,
    MarketConflictError,
    create_asset,
    create_instrument,
    list_assets,
    list_instruments,
    update_asset,
    update_instrument,
)


router = APIRouter(tags=["market catalog"])


@router.get("/assets", response_model=list[AssetRead])
def read_assets(db: DbSession) -> list[AssetRead]:
    return [AssetRead.model_validate(asset) for asset in list_assets(db)]


@router.post(
    "/assets",
    response_model=AssetRead,
    status_code=status.HTTP_201_CREATED,
)
def add_asset(
    data: AssetWrite,
    db: DbSession,
    _admin: AdminUser,
) -> AssetRead:
    try:
        asset = create_asset(db, data)
    except MarketConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An asset with this symbol already exists",
        ) from exc
    return AssetRead.model_validate(asset)


@router.put("/assets/{asset_id}", response_model=AssetRead)
def edit_asset(
    asset_id: int,
    data: AssetWrite,
    db: DbSession,
    _admin: AdminUser,
) -> AssetRead:
    try:
        asset = update_asset(db, asset_id, data)
    except AssetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        ) from exc
    except MarketConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An asset with this symbol already exists",
        ) from exc
    return AssetRead.model_validate(asset)


@router.get("/instruments", response_model=list[InstrumentRead])
def read_instruments(db: DbSession) -> list[InstrumentRead]:
    return [
        InstrumentRead.model_validate(instrument)
        for instrument in list_instruments(db)
    ]


@router.post(
    "/instruments",
    response_model=InstrumentRead,
    status_code=status.HTTP_201_CREATED,
)
def add_instrument(
    data: InstrumentWrite,
    db: DbSession,
    _admin: AdminUser,
) -> InstrumentRead:
    try:
        instrument = create_instrument(db, data)
    except InvalidInstrumentError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except MarketConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This trading instrument already exists",
        ) from exc
    return InstrumentRead.model_validate(instrument)


@router.put("/instruments/{instrument_id}", response_model=InstrumentRead)
def edit_instrument(
    instrument_id: int,
    data: InstrumentWrite,
    db: DbSession,
    _admin: AdminUser,
) -> InstrumentRead:
    try:
        instrument = update_instrument(db, instrument_id, data)
    except InstrumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trading instrument not found",
        ) from exc
    except InvalidInstrumentError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except MarketConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This trading instrument already exists",
        ) from exc
    return InstrumentRead.model_validate(instrument)
