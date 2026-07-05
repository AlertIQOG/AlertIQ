"""Embedding service — the single isolation point for the embedding provider.

Provider is chosen by ``settings.EMBEDDING_PROVIDER`` ("voyage" or "google").
Retrieval, storage and the API never talk to a provider directly; they go
through ``embedding_service`` so the provider can be swapped in one place.

Both providers use *asymmetric* embeddings: stored documents and search queries
get different task hints (Voyage ``input_type``; Google ``task_type``).
"""

from app.core.config import settings
from app.core.exceptions import ConfigurationError

# Per-request input caps differ by provider; batch under them for backfills.
_VOYAGE_BATCH = 128
_GOOGLE_BATCH = 100


class EmbeddingService:
    """Turns text into vectors via the configured provider. Clients are lazy."""

    def __init__(self) -> None:
        self._voyage_client = None  # type: ignore[var-annotated]
        self._google_client = None  # type: ignore[var-annotated]

    @property
    def provider(self) -> str:
        return settings.EMBEDDING_PROVIDER.lower()

    @property
    def model(self) -> str:
        """Active embedding model name (stored on each chunk for idempotency)."""
        if self.provider == "google":
            return settings.GOOGLE_EMBEDDING_MODEL
        return settings.EMBEDDING_MODEL

    def is_configured(self) -> bool:
        """True when the active provider has an API key."""
        if self.provider == "google":
            return bool(settings.GOOGLE_API_KEY)
        return bool(settings.VOYAGE_API_KEY)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed stored documents (document task hint)."""
        if not texts:
            return []
        if self.provider == "google":
            return self._embed_google(texts, "RETRIEVAL_DOCUMENT")
        return self._embed_voyage(texts, "document")

    def embed_query(self, text: str) -> list[float]:
        """Embed a single search query (query task hint)."""
        if self.provider == "google":
            return self._embed_google([text], "RETRIEVAL_QUERY")[0]
        return self._embed_voyage([text], "query")[0]

    # ── Voyage ────────────────────────────────────────────────────────

    @property
    def _voyage(self):  # noqa: ANN202 — third-party client type
        if self._voyage_client is None:
            if not settings.VOYAGE_API_KEY:
                raise ConfigurationError(
                    "VOYAGE_API_KEY is not set; cannot embed text."
                )
            import voyageai

            self._voyage_client = voyageai.Client(api_key=settings.VOYAGE_API_KEY)
        return self._voyage_client

    def _embed_voyage(self, texts: list[str], input_type: str) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for start in range(0, len(texts), _VOYAGE_BATCH):
            batch = texts[start : start + _VOYAGE_BATCH]
            result = self._voyage.embed(
                batch, model=settings.EMBEDDING_MODEL, input_type=input_type
            )
            embeddings.extend(result.embeddings)
        return embeddings

    # ── Google ────────────────────────────────────────────────────────

    @property
    def _google(self):  # noqa: ANN202 — third-party client type
        if self._google_client is None:
            if not settings.GOOGLE_API_KEY:
                raise ConfigurationError(
                    "GOOGLE_API_KEY is not set; cannot embed text."
                )
            from google import genai

            self._google_client = genai.Client(api_key=settings.GOOGLE_API_KEY)
        return self._google_client

    def _embed_google(self, texts: list[str], task_type: str) -> list[list[float]]:
        from google.genai import types

        embeddings: list[list[float]] = []
        for start in range(0, len(texts), _GOOGLE_BATCH):
            batch = texts[start : start + _GOOGLE_BATCH]
            result = self._google.models.embed_content(
                model=settings.GOOGLE_EMBEDDING_MODEL,
                contents=batch,
                config=types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=settings.EMBEDDING_DIM,
                ),
            )
            embeddings.extend([e.values for e in result.embeddings])
        return embeddings


embedding_service = EmbeddingService()
