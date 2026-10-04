from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(
        min_length=8,
        max_length=128,
        repr=False, # не показывет пароль при выводе в лог
        json_schema_extra={"format": "password"},
    )


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(
        min_length=8,
        max_length=128,
        repr=False,
        json_schema_extra={"format": "password"},
    )


class Token(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"