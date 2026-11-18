"""A deterministic provider for tests and for reproducing the pipeline without an API key.

Token counts here are rough estimates (4 characters per token). They exist so the pricing,
budget and logging code can be exercised. They are never used for a real run.
"""

from __future__ import annotations

from collections.abc import Callable

from aca.providers.base import Message, Response, Usage

Responder = Callable[[str, str, list[Message]], str]
"""(model, system, messages) -> reply text."""

CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    """Rough token estimate for the mock only."""
    return max(1, len(text) // CHARS_PER_TOKEN)


def _default_responder(model: str, system: str, messages: list[Message]) -> str:
    return "```python\ndef solution():\n    return None\n```"


class MockProvider:
    """Returns scripted replies and simulates a per-model system-prompt cache."""

    name = "mock"

    def __init__(
        self,
        responder: Responder | None = None,
        *,
        latency_ms: float = 1.0,
        min_cacheable_tokens: int = 512,
    ) -> None:
        self._responder = responder or _default_responder
        self._latency_ms = latency_ms
        self._min_cacheable_tokens = min_cacheable_tokens
        self._cached: set[tuple[str, str]] = set()
        self.calls: list[dict] = []

    def complete(
        self,
        messages: list[Message],
        system: str,
        cache: bool,
        *,
        model: str,
        max_tokens: int,
    ) -> Response:
        text = self._responder(model, system, messages)
        system_tokens = estimate_tokens(system)
        message_tokens = sum(estimate_tokens(m["content"]) for m in messages)

        usage = Usage(
            input_tokens=system_tokens + message_tokens,
            output_tokens=min(estimate_tokens(text), max_tokens),
        )
        if cache and system_tokens >= self._min_cacheable_tokens:
            key = (model, system)
            if key in self._cached:
                usage = usage.model_copy(
                    update={"input_tokens": message_tokens, "cache_read_tokens": system_tokens}
                )
            else:
                self._cached.add(key)
                usage = usage.model_copy(
                    update={"input_tokens": message_tokens, "cache_write_5m_tokens": system_tokens}
                )

        self.calls.append({"model": model, "cache": cache, "messages": messages})
        return Response(
            text=text,
            model=model,
            usage=usage,
            latency_ms=self._latency_ms,
            stop_reason="end_turn",
        )
