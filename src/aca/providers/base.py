"""The single interface every model provider implements."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field

Message = dict[str, str]
"""A chat message: {"role": "user" | "assistant", "content": "..."}."""


class Usage(BaseModel):
    """Token counts for one call, as reported by the provider's usage fields."""

    input_tokens: int = Field(default=0, ge=0)
    """Prompt tokens billed at the base input rate (not written to or read from cache)."""
    output_tokens: int = Field(default=0, ge=0)
    cache_write_5m_tokens: int = Field(default=0, ge=0)
    cache_write_1h_tokens: int = Field(default=0, ge=0)
    cache_read_tokens: int = Field(default=0, ge=0)

    @property
    def cache_write_tokens(self) -> int:
        return self.cache_write_5m_tokens + self.cache_write_1h_tokens

    @property
    def prompt_tokens(self) -> int:
        """Every token in the prompt, whichever rate it was billed at."""
        return self.input_tokens + self.cache_write_tokens + self.cache_read_tokens


class Response(BaseModel):
    """What a provider returns for one call."""

    text: str
    model: str
    """The model that actually served the call. Costs are priced from this, not the request."""
    usage: Usage
    latency_ms: float = Field(ge=0)
    stop_reason: str | None = None


class Provider(Protocol):
    """One model provider. Calls are stateless: the caller sends the full context each time."""

    name: str

    def complete(
        self,
        messages: list[Message],
        system: str,
        cache: bool,
        *,
        model: str,
        max_tokens: int,
    ) -> Response:
        """Run one model call. `cache` asks the provider to cache the system prompt."""
        ...
