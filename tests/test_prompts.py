from __future__ import annotations

from aca import prompts
from aca.providers.mock import estimate_tokens


def test_system_prompt_is_long_enough_to_cache() -> None:
    # The published minimum for the models used is 512 tokens. Keep a wide margin.
    # The exact count per model is checked against the API before a real run.
    assert estimate_tokens(prompts.system_prompt("x")) > 1500


def test_policies_differ_only_in_the_label_line() -> None:
    a = prompts.system_prompt("opus_cached")
    b = prompts.system_prompt("routed_cached")
    assert a != b
    assert a.splitlines()[1:] == b.splitlines()[1:]
    assert a.startswith("Pipeline label: opus_cached\n")


def test_system_prompt_is_stable() -> None:
    assert prompts.system_prompt("p") == prompts.system_prompt("p")
    assert len(prompts.body_sha256()) == 64


def test_system_prompt_holds_no_volatile_content() -> None:
    text = prompts.system_prompt("p")
    for marker in ("{", "}", "20", "today", "date:"):
        assert marker not in text.replace("3.12", "").replace("512", ""), marker
