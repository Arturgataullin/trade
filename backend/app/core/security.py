import hashlib
import hmac
from datetime import datetime, timedelta, timezone

import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash

from backend.app.core.config import settings


password_hash = PasswordHash.recommended()


class InvalidAccessTokenError(ValueError):
    """Raised when an access token is invalid or expired."""


def _apply_password_pepper(password: str) -> str:
    pepper = settings.password_pepper.get_secret_value().encode("utf-8")

    return hmac.new(
        key=pepper,
        msg=password.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()


def hash_password(password: str) -> str:
    peppered_password = _apply_password_pepper(password)
    return password_hash.hash(peppered_password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    peppered_password = _apply_password_pepper(plain_password)

    return password_hash.verify(
        peppered_password,
        hashed_password,
    )


def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
) -> str:
    now = datetime.now(timezone.utc)

    if expires_delta is None:
        expires_delta = timedelta(
            minutes=settings.jwt_expire_minutes,
        )

    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + expires_delta,
    }

    return jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            options={
                "require": ["sub", "iat", "exp"],
            },
        )
    except InvalidTokenError as exc:
        raise InvalidAccessTokenError(
            "Invalid or expired access token"
        ) from exc

    subject = payload.get("sub")

    if not isinstance(subject, str) or not subject:
        raise InvalidAccessTokenError(
            "Access token subject is missing"
        )

    return subject