from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from backend.app.models.user import User  # noqa: E402, F401