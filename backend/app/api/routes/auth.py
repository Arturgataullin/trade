from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.security import create_access_token
from backend.app.db.dependencies import get_db
from backend.app.schemas.auth import LoginRequest, Token, UserCreate
from backend.app.schemas.user import UserRead
from backend.app.services.auth import (
    EmailAlreadyRegisteredError,
    authenticate_user,
    register_user,
)


router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


DbSession = Annotated[Session, Depends(get_db)]


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
def register(
    data: UserCreate,
    db: DbSession,
) -> UserRead:
    try:
        user = register_user(db, data)
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered",
        ) from exc

    return UserRead.model_validate(user)


@router.post(
    "/login",
    response_model=Token,
)
def login(
    data: LoginRequest,
    db: DbSession,
) -> Token:
    user = authenticate_user(
        db,
        email=str(data.email),
        password=data.password,
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    access_token = create_access_token(
        subject=str(user.id),
    )

    return Token(
        access_token=access_token,
    )