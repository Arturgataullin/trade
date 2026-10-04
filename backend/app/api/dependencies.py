from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.app.core.security import (
    InvalidAccessTokenError,
    decode_access_token,
)
from backend.app.db.dependencies import get_db
from backend.app.models.user import User


bearer_scheme = HTTPBearer(
    auto_error=False,
)


DbSession = Annotated[
    Session,
    Depends(get_db),
]


BearerCredentials = Annotated[
    HTTPAuthorizationCredentials | None,
    Depends(bearer_scheme),
]


def credentials_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={
            "WWW-Authenticate": "Bearer",
        },
    )


def get_current_user(
    credentials: BearerCredentials,
    db: DbSession,
) -> User:
    if credentials is None:
        raise credentials_exception()

    if credentials.scheme.lower() != "bearer":
        raise credentials_exception()

    try:
        subject = decode_access_token(
            credentials.credentials
        )
    except InvalidAccessTokenError as exc:
        raise credentials_exception() from exc

    try:
        user_id = int(subject)
    except ValueError as exc:
        raise credentials_exception() from exc

    user = db.get(User, user_id)

    if user is None:
        raise credentials_exception()

    if not user.is_active:
        raise credentials_exception()

    return user


CurrentUser = Annotated[
    User,
    Depends(get_current_user),
]