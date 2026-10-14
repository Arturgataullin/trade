"""Promote an existing user to administrator from the server console."""

import argparse

from backend.app.db.session import SessionLocal
from backend.app.services.auth import get_user_by_email


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email", help="Email of an existing registered user")
    args = parser.parse_args()

    with SessionLocal() as db:
        user = get_user_by_email(db, args.email)
        if user is None:
            parser.error("User not found")

        user.role = "admin"
        db.commit()
        print(f"Administrator role granted to {user.email}")


if __name__ == "__main__":
    main()
