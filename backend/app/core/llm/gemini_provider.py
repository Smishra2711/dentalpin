"""Gemini implementation of the neutral :class:`Provider` protocol.

Speaks Google's OpenAI-compatible endpoint
(``https://generativelanguage.googleapis.com/v1beta/openai/``) through the
``openai`` SDK, so the wire format — Chat Completions streaming, tool
calling, usage chunks — is identical to :class:`OpenAIProvider` and this
subclass only sets the endpoint and the key. Tool dialect is ``"openai"``;
dotted tool names map ``.`` <-> ``-`` exactly like the OpenAI provider.

Quota/terms note: a Gemini API key from AI Studio serves the free tier,
whose data-use terms the clinic operator accepts in Google AI Studio.
DentalPin always offers Gemini opt-in (deployment key + per-clinic
selection) and the mandatory PHI redactor runs upstream of every provider.
"""

from __future__ import annotations

from app.core.llm.base import LLMConfigError
from app.core.llm.openai_provider import OpenAIProvider

#: Google's OpenAI-compatible chat-completions base URL
#: (https://ai.google.dev/gemini-api/docs/openai).
GEMINI_OPENAI_COMPAT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


class GeminiProvider(OpenAIProvider):
    """Streams completions from Gemini, speaking neutral types."""

    def __init__(self, *, api_key: str) -> None:
        if not api_key:
            raise LLMConfigError("Gemini provider requires GEMINI_API_KEY")
        super().__init__(api_key=api_key, base_url=GEMINI_OPENAI_COMPAT_BASE_URL)
