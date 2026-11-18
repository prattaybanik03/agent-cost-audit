"""The Anthropic provider, tested against a fake client. No network calls are made."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from aca.providers.anthropic import (
    AnthropicProvider,
    conservative_token_estimate,
    reply_text,
    usage_from_api,
)


def api_usage(**fields):
    defaults = {
        "input_tokens": 100,
        "output_tokens": 50,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "cache_creation": None,
    }
    defaults.update(fields)
    return SimpleNamespace(**defaults)


class FakeMessages:
    def __init__(self, response):
        self.response = response
        self.requests: list[dict] = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return self.response


def fake_client(text="```python\nx = 1\n```", usage=None, model="claude-haiku-5-5"):
    response = SimpleNamespace(
        content=[
            SimpleNamespace(type="thinking", thinking=""),
            SimpleNamespace(type="text", text=text),
        ],
        model=model,
        usage=usage or api_usage(),
        stop_reason="end_turn",
    )
    return SimpleNamespace(messages=FakeMessages(response))


def call(provider, cache):
    return provider.complete(
        [{"role": "user", "content": "hi"}],
        "SYSTEM",
        cache,
        model="claude-haiku-5-5",
        max_tokens=1000,
    )


def test_cache_marker_is_added_only_when_asked() -> None:
    client = fake_client()
    provider = AnthropicProvider(effort="medium", client=client)
    call(provider, cache=False)
    call(provider, cache=True)
    plain, cached = client.messages.requests
    assert plain["system"] == [{"type": "text", "text": "SYSTEM"}]
    assert cached["system"] == [
        {"type": "text", "text": "SYSTEM", "cache_control": {"type": "ephemeral"}}
    ]


def test_request_pins_effort_and_sends_no_fallback() -> None:
    client = fake_client()
    call(AnthropicProvider(effort="medium", client=client), cache=False)
    request = client.messages.requests[0]
    assert request["output_config"] == {"effort": "medium"}
    assert request["model"] == "claude-haiku-5-5"
    assert request["max_tokens"] == 1000
    assert "fallbacks" not in request and "betas" not in request
    assert "thinking" not in request


def test_response_maps_text_model_usage_and_latency() -> None:
    usage = api_usage(input_tokens=40, output_tokens=900, cache_read_input_tokens=2000)
    client = fake_client(usage=usage, model="claude-opus-5-5")
    response = call(AnthropicProvider(effort="medium", client=client), cache=True)
    assert response.text == "```python\nx = 1\n```"
    assert response.model == "claude-opus-5-5"
    assert response.usage.cache_read_tokens == 2000
    assert response.usage.output_tokens == 900
    assert response.latency_ms >= 0
    assert response.stop_reason == "end_turn"


def test_thinking_blocks_are_not_part_of_the_reply() -> None:
    blocks = [
        SimpleNamespace(type="thinking", thinking="secret"),
        SimpleNamespace(type="text", text="a"),
        SimpleNamespace(type="text", text="b"),
    ]
    assert reply_text(blocks) == "ab"


def test_cache_writes_are_split_by_lifetime() -> None:
    breakdown = SimpleNamespace(ephemeral_5m_input_tokens=300, ephemeral_1h_input_tokens=200)
    usage = usage_from_api(api_usage(cache_creation_input_tokens=500, cache_creation=breakdown))
    assert usage.cache_write_5m_tokens == 300
    assert usage.cache_write_1h_tokens == 200
    assert usage.cache_write_tokens == 500


def test_cache_writes_without_a_breakdown_count_as_five_minute() -> None:
    usage = usage_from_api(api_usage(cache_creation_input_tokens=700))
    assert usage.cache_write_5m_tokens == 700
    assert usage.cache_write_1h_tokens == 0


def test_inconsistent_cache_breakdown_is_an_error() -> None:
    breakdown = SimpleNamespace(ephemeral_5m_input_tokens=1, ephemeral_1h_input_tokens=1)
    with pytest.raises(ValueError):
        usage_from_api(api_usage(cache_creation_input_tokens=500, cache_creation=breakdown))


def test_missing_cache_fields_count_as_zero() -> None:
    usage = usage_from_api(SimpleNamespace(input_tokens=5, output_tokens=6))
    assert usage.cache_write_tokens == 0 and usage.cache_read_tokens == 0


def test_conservative_estimate_overestimates_typical_text() -> None:
    text = "def merge(intervals):\n    return sorted(intervals)\n" * 50
    # Code averages well above two characters per token, so this is a safe upper bound.
    assert conservative_token_estimate(text) > len(text) / 3
