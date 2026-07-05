"""
Bootstrap the first admin user.

There is no self-service registration — users are created by an admin, and
the first admin is created by this script:

    python -m app.scripts.create_admin <username> <password> [full name]

Idempotent: exits with a message if the username already exists.
"""

import sys

from sqlmodel import Session

from app.core.database import engine
from app.models.user import UserRole
from app.schemas.user import UserCreate
from app.services.user import user_service


def main() -> None:
    if len(sys.argv) < 3:
        print(
            "Usage: python -m app.scripts.create_admin "
            "<username> <password> [full name]"
        )
        raise SystemExit(1)

    username, password = sys.argv[1], sys.argv[2]
    full_name = " ".join(sys.argv[3:]) or None

    with Session(engine) as session:
        if user_service.get_by_username(session, username=username):
            print(f"User '{username}' already exists — nothing to do.")
            return
        user = user_service.create_user(
            session,
            obj_in=UserCreate(
                username=username,
                password=password,
                full_name=full_name,
                role=UserRole.ADMIN,
            ),
        )
        print(f"Admin user '{user.username}' created (id={user.id}).")


if __name__ == "__main__":
    main()
