"""
User service — account management and credential verification.

Speaks only in domain models and domain exceptions, per the service-layer
rules (no FastAPI imports, no HTTP status codes).
"""

from sqlmodel import Session, select

from app.core.exceptions import ConflictError
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.user import UserCreate
from app.services.base import CRUDBase


class UserService(CRUDBase[User]):
    """CRUD plus authentication logic for users."""

    def get_by_username(self, session: Session, *, username: str) -> User | None:
        """Return the user with the given username, or ``None``."""
        statement = select(User).where(User.username == username)
        return session.exec(statement).first()

    def create_user(self, session: Session, *, obj_in: UserCreate) -> User:
        """Create a user, hashing the password. Raises on duplicate username."""
        if self.get_by_username(session, username=obj_in.username):
            raise ConflictError(f"Username '{obj_in.username}' already exists")

        user = User(
            username=obj_in.username,
            hashed_password=hash_password(obj_in.password),
            full_name=obj_in.full_name,
            role=obj_in.role,
        )
        return self.create(session, obj_in=user)

    def authenticate(
        self, session: Session, *, username: str, password: str
    ) -> User | None:
        """
        Verify credentials. Returns the user on success, ``None`` otherwise.

        Inactive users cannot authenticate.
        """
        user = self.get_by_username(session, username=username)
        if user is None:
            return None
        if not user.is_active:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user


user_service = UserService(User)
