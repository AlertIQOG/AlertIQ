"""Generation — turns retrieved precedents into a grounded, cited suggestion.

The provider (Anthropic Claude or Google Gemini) is selected by
``settings.LLM_PROVIDER`` and isolated behind ``GenerationService.generate`` so
retrieval, storage, and the API never depend on a specific LLM.

Both providers are forced to emit the same fixed structure via structured
output: Claude through a single ``strict`` tool (``tool_choice`` pinned to it),
Gemini through a JSON ``response_schema``.
"""

import json

from app.core.config import settings
from app.core.exceptions import ConfigurationError, GenerationError
from app.services.rag.retriever import RetrievalHit

_TOOL_NAME = "provide_resolution_suggestion"

# The fixed result shape, shared by both providers. Per-step ``citations`` are a
# required array but may be empty — an empty array marks a generic-triage step
# the retrieved context does not specifically support.
SUGGESTION_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "diagnosis": {
            "type": "string",
            "description": "Likely root cause, grounded in the numbered context.",
        },
        "steps": {
            "type": "array",
            "description": "Ordered remediation steps.",
            "items": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "A single concrete remediation action.",
                    },
                    "citations": {
                        "type": "array",
                        "description": (
                            "Context block numbers supporting this step; empty "
                            "for generic-triage steps the context does not support."
                        ),
                        "items": {"type": "integer"},
                    },
                },
                "required": ["action", "citations"],
                "additionalProperties": False,
            },
        },
        "confidence": {
            "type": "string",
            "enum": ["high", "medium", "low"],
            "description": "Overall confidence in the suggestion.",
        },
    },
    "required": ["diagnosis", "steps", "confidence"],
    "additionalProperties": False,
}

def _gemini_schema(schema: dict | list | object) -> object:
    """Gemini's ``response_schema`` rejects ``additionalProperties`` (which Claude's
    strict tool requires). Recursively drop it for the Gemini path only.
    """
    if isinstance(schema, dict):
        return {
            k: _gemini_schema(v)
            for k, v in schema.items()
            if k != "additionalProperties"
        }
    if isinstance(schema, list):
        return [_gemini_schema(item) for item in schema]
    return schema


SYSTEM_PROMPT = (
    "You are AlertIQ's Resolution Copilot. An on-call operator is triaging an "
    "alert. You are given numbered context blocks: past RESOLVED alerts and "
    "incidents, each including how it was actually fixed.\n\n"
    "Your job: produce a concrete, grounded remediation suggestion.\n\n"
    "Grounding rules:\n"
    "- Base your answer on the numbered context blocks. Whenever a step is drawn "
    "from a block, put that block's number in that step's `citations` array. "
    "Do NOT write citation markers like '(1)' in the diagnosis or step prose — "
    "citations belong ONLY in the `citations` arrays.\n"
    "- Prefer the SPECIFIC remediation shown in the precedents' resolution notes "
    "(exact commands, config or limit changes, root causes) over generic advice. "
    "Adapt the details to this alert and cite the block you took them from.\n"
    "- A step that is general best practice and not drawn from any block may "
    "have an empty `citations` array.\n\n"
    "If at least one block clearly matches, you MUST reuse its specific actions "
    "and cite it — an answer with relevant blocks but no citations on any step is "
    "wrong.\n\n"
    "Example — given a block [2] whose resolution note says 'Cleared archived WAL "
    "logs with pg_archivecleanup and expanded the volume', a good step is:\n"
    '  {"action": "Clear archived WAL logs with pg_archivecleanup, then expand '
    'the volume if usage stays high (as in the prior payments-db disk alert).", '
    '"citations": [2]}\n\n'
    "Confidence:\n"
    "- 'high': a precedent closely matches this alert and includes a resolution.\n"
    "- 'medium': precedents are related but not an exact match.\n"
    "- 'low': no precedent genuinely supports a specific fix — give clearly "
    "labeled generic triage only.\n\n"
    "Never invent block numbers; only cite blocks that exist."
)


def build_context_blocks(hits: list[RetrievalHit]) -> str:
    """Render retrieved hits as numbered blocks the model can cite by number."""
    blocks = []
    for i, hit in enumerate(hits, start=1):
        blocks.append(f"[{i}] (similarity {hit.similarity:.2f})\n{hit.content}")
    return "\n\n".join(blocks)


def build_user_prompt(alert_text: str, hits: list[RetrievalHit]) -> str:
    """Assemble the user message: the alert under triage + numbered precedents."""
    return (
        "Alert under triage:\n"
        f"{alert_text}\n\n"
        "Context blocks (past precedents):\n"
        f"{build_context_blocks(hits)}\n\n"
        "Produce a grounded resolution suggestion citing the blocks by number."
    )


class GenerationService:
    """Single isolation point for the generation LLM provider."""

    def __init__(self) -> None:
        self._anthropic = None  # type: ignore[var-annotated]
        self._google = None  # type: ignore[var-annotated]

    @property
    def provider(self) -> str:
        return settings.LLM_PROVIDER

    def is_configured(self) -> bool:
        """True when the configured provider has an API key."""
        if settings.LLM_PROVIDER.lower() == "google":
            return bool(settings.GOOGLE_API_KEY)
        return bool(settings.ANTHROPIC_API_KEY)

    def generate(self, *, system: str, user: str) -> dict:
        """Return a dict matching ``SUGGESTION_SCHEMA`` from the active provider."""
        provider = settings.LLM_PROVIDER.lower()
        if provider == "google":
            return self._generate_google(system, user)
        if provider == "anthropic":
            return self._generate_anthropic(system, user)
        raise ConfigurationError(f"Unknown LLM_PROVIDER: {settings.LLM_PROVIDER!r}")

    def _generate_anthropic(self, system: str, user: str) -> dict:
        if not settings.ANTHROPIC_API_KEY:
            raise ConfigurationError(
                "ANTHROPIC_API_KEY is not set; cannot generate a suggestion."
            )
        import anthropic

        if self._anthropic is None:
            self._anthropic = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

        response = self._anthropic.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=4096,
            system=system,
            tools=[
                {
                    "name": _TOOL_NAME,
                    "description": "Return the grounded resolution suggestion.",
                    "strict": True,
                    "input_schema": SUGGESTION_SCHEMA,
                }
            ],
            tool_choice={"type": "tool", "name": _TOOL_NAME},
            messages=[{"role": "user", "content": user}],
        )
        for block in response.content:
            if block.type == "tool_use":
                return dict(block.input)
        raise GenerationError("Claude did not return a structured suggestion.")

    def _generate_google(self, system: str, user: str) -> dict:
        if not settings.GOOGLE_API_KEY:
            raise ConfigurationError(
                "GOOGLE_API_KEY is not set; cannot generate a suggestion."
            )
        from google import genai
        from google.genai import types

        if self._google is None:
            self._google = genai.Client(api_key=settings.GOOGLE_API_KEY)

        response = self._google.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                response_schema=_gemini_schema(SUGGESTION_SCHEMA),
            ),
        )
        try:
            return json.loads(response.text)
        except (json.JSONDecodeError, TypeError) as exc:
            raise GenerationError(
                "Gemini did not return valid JSON for the suggestion."
            ) from exc


generation_service = GenerationService()
