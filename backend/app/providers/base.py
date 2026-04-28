"""
Contract for provider adapters.

Every provider module must expose a normalizer object whose ``normalize``
method satisfies the ``AlertNormalizer`` protocol.  No inheritance required —
structural (duck-typed) matching is enough.
"""

import uuid
from typing import Any, Protocol

from app.schemas.alert import AlertCreate


class AlertNormalizer(Protocol):
    """Structural contract that every provider normalizer must satisfy."""

    def normalize(
        self,
        source_id: uuid.UUID,
        payload: Any,
    ) -> list[AlertCreate]:
        """Convert a provider-native webhook payload into a list of AlertCreate objects."""
        ...
