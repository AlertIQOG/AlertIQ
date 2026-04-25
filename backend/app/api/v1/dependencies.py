"""
Shared FastAPI dependencies for API v1 routes.
"""

from typing import Annotated

from fastapi import Depends, Query
from sqlmodel import Session

from app.core.database import get_session

# Re-usable annotated dependency — avoids repeating ``Depends(get_session)``
# in every single endpoint signature.
DbSession = Annotated[Session, Depends(get_session)]


class PaginationParams:
    """
    Standard pagination query parameters.

    Usage in a route:
        def list_items(pagination: PaginationParams = Depends()):
    """

    def __init__(
        self,
        skip: int = Query(0, ge=0, description="Records to skip"),
        limit: int = Query(100, ge=1, le=500, description="Max records to return"),
    ) -> None:
        self.skip = skip
        self.limit = limit
