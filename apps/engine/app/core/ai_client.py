"""Thin wrapper around the Anthropic client. One place that reads the API
key, so nothing else has to touch settings.anthropic_api_key directly."""

from anthropic import Anthropic

from app.core.config import settings

# Used for both OCR (vision transcription) and structured extraction.
# See CLAUDE.md section 5 for why Claude fills both roles, and for the
# explicit decision to use Opus 5 despite the higher cost.
DEFAULT_MODEL = "claude-opus-5"


def get_anthropic_client() -> Anthropic:
    if not settings.anthropic_api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Add it to apps/engine/.env."
        )
    return Anthropic(api_key=settings.anthropic_api_key)
