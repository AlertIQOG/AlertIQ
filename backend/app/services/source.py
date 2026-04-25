"""Source-specific service logic."""

from app.models.source import Source
from app.services.base import CRUDBase


class SourceService(CRUDBase[Source]):
    """
    Source service — inherits all generic CRUD operations.

    Add provider-specific business rules here as the domain grows
    (e.g. validate webhook URLs, test connectivity, etc.).
    """


source_service = SourceService(Source)
