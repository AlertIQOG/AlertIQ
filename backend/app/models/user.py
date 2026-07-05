import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Column, DateTime, func
from sqlmodel import Field, SQLModel


class UserRole(str, Enum):
    ADMIN = "Admin"
    OPERATOR = "Operator"
    VIEWER = "Viewer"


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    username: str = Field(index=True, unique=True)
    hashed_password: str
    full_name: str | None = Field(default=None)
    role: UserRole = Field(default=UserRole.OPERATOR)
    is_active: bool = Field(default=True)
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True), server_default=func.now(), nullable=False
        ),
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        ),
    )
