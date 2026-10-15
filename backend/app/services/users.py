from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.user import User


class UserNotFoundError(Exception):
    """Raised when the requested user does not exist."""


def list_users(db: Session) -> list[User]:
    statement = select(User).order_by(User.id)
    return list(db.scalars(statement).all())


def change_user_role(db: Session, user_id: int, role: str) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise UserNotFoundError

    user.role = role
    db.commit()
    db.refresh(user)
    return user
