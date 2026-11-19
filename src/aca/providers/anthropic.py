"""The Anthropic Messages API provider.

Token counts come from the response's usage fields. Nothing here estimates them, except
`conservative_token_estimate`, which only sizes the budget reservation before a call.

Refusal fallback is not enabled: it would let a different model serve a call, which would mix
models inside a policy. A refusal comes back as stop_reason "refusal" and fails that step.
"""

from __future__ import annotations

import time
from typing import Any, cast

import anthropic
from anthropic.types import MessageParam, OutputConfigParam, TextBlockParam

from aca.providers.base import Message, Response, Usage

DEFAULT_MAX_RETRIES = 5
DEFAULT_TIMEOUT_S = 600.0


def conservative_token_estimate(text: str) -> int:
    """An over-estimate of the token count, for the budget check only.

    Real text averages roughly 3 to 4 characters per token. Two characters per token, plus a
    margin, keeps the reservation above the real figure.
    """
    return len(text) // 2 + 64


def usage_from_api(usage: Any) -> Usage:
    """Map the API's usage object onto ours, splitting cache writes by lifetime when reported."""
    write_total = getattr(usage, "cache_creation_input_tokens", None) or 0
    write_5m, write_1h = write_total, 0
    breakdown = getattr(usage, "cache_creation", None)
    if breakdown is not None:
        write_5m = getattr(breakdown, "ephemeral_5m_input_tokens", None) or 0
        write_1h = getattr(breakdown, "ephemeral_1h_input_tokens", None) or 0
        if write_5m + write_1h != write_total:
            raise ValueError(
                f"Cache write breakdown {write_5m}+{write_1h} does not match total {write_total}."
            )
    return Usage(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_write_5m_tokens=write_5m,
        cache_write_1h_tokens=write_1h,
        cache_read_tokens=getattr(usage, "cache_read_input_tokens", None) or 0,
    )


def reply_text(content: list[Any]) -> str:
    """Join the text blocks of a reply. Thinking blocks are not part of the answer."""
    return "".join(block.text for block in content if getattr(block, "type", None) == "text")


class AnthropicProvider:
    name = "anthropic"

    def __init__(
        self,
        *,
        effort: str,
        client: Any | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        self.effort = effort
        self._client = client or anthropic.Anthropic(max_retries=max_retries, timeout=timeout_s)

    def complete(
        self,
        messages: list[Message],
        system: str,
        cache: bool,
        *,
        model: str,
        max_tokens: int,
    ) -> Response:
        block: TextBlockParam = {"type": "text", "text": system}
        if cache:
            block["cache_control"] = {"type": "ephemeral"}
        # Our messages are plain role/content dicts, which is the shape MessageParam describes.
        api_messages = cast(list[MessageParam], messages)
        output_config = cast(OutputConfigParam, {"effort": self.effort})

        # Streamed so a large output allowance cannot hit an HTTP timeout. Only the final
        # message is used; latency is the time to the complete reply.
        started = time.perf_counter()
        with self._client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            system=[block],
            messages=api_messages,
            output_config=output_config,
        ) as stream:
            response = stream.get_final_message()
        latency_ms = (time.perf_counter() - started) * 1000

        return Response(
            text=reply_text(response.content),
            model=response.model,
            usage=usage_from_api(response.usage),
            latency_ms=latency_ms,
            stop_reason=response.stop_reason,
        )

    def count_system_tokens(self, system: str, model: str) -> int:
        """Exact token count of a system prompt for one model. Free; used to check caching."""
        result = self._client.messages.count_tokens(
            model=model,
            system=[{"type": "text", "text": system}],
            messages=[{"role": "user", "content": "x"}],
        )
        return result.input_tokens
