from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator


Symbol = Annotated[str, Field(min_length=1, max_length=16)]
AssetName = Annotated[str, Field(min_length=1, max_length=128)]


class AssetWrite(BaseModel):
    symbol: Symbol
    name: AssetName
    is_active: bool = True

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("Symbol must not be empty")
        return normalized

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Name must not be empty")
        return normalized


class AssetRead(BaseModel):
    id: int
    symbol: str
    name: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class InstrumentWrite(BaseModel):
    base_asset_id: int = Field(gt=0)
    quote_asset_id: int = Field(gt=0)
    is_active: bool = True


class InstrumentRead(BaseModel):
    id: int
    base_asset_id: int
    quote_asset_id: int
    is_active: bool
    base_asset: AssetRead
    quote_asset: AssetRead

    model_config = ConfigDict(from_attributes=True)
