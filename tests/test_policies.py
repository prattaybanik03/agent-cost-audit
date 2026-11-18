from __future__ import annotations

import pytest
from pydantic import ValidationError

from aca.policies import RunConfig
from aca.pricing import PriceTable, PricingError


def base_config(**overrides) -> dict:
    data = {
        "budget_cap_usd": 5.0,
        "repetitions": 2,
        "max_fix_attempts": 2,
        "max_tokens": 1000,
        "effort": "medium",
        "models": {"big": "claude-opus-5-5", "small": "claude-haiku-5-5"},
        "baseline": "big_only",
        "policies": [
            {"name": "big_only", "plan": "big", "write": "big", "fix": ["big", "big"]},
            {
                "name": "routed",
                "plan": "big",
                "write": "small",
                "fix": ["small", "big"],
                "cache": True,
            },
        ],
    }
    data.update(overrides)
    return data


def test_shipped_config_loads_and_every_model_is_priced(
    config: RunConfig, prices: PriceTable
) -> None:
    config.check_priced(prices)
    assert config.baseline in [p.name for p in config.policies]
    assert config.budget_cap_usd > 0


def test_shipped_cached_policies_differ_from_their_pair_only_by_caching(
    config: RunConfig,
) -> None:
    for policy in config.policies:
        if not policy.name.endswith("_cached"):
            continue
        plain = config.policy(policy.name.removesuffix("_cached"))
        assert policy.cache and not plain.cache
        assert policy.steps() == plain.steps()


def test_model_ids_resolve() -> None:
    config = RunConfig.model_validate(base_config())
    routed = config.policy("routed")
    assert config.model_id(routed.plan) == "claude-opus-5-5"
    assert config.model_id(routed.write) == "claude-haiku-5-5"
    assert routed.cache is True
    assert config.policy("big_only").cache is False


def test_fix_list_must_match_max_fix_attempts() -> None:
    with pytest.raises(ValidationError, match="fix models"):
        RunConfig.model_validate(base_config(max_fix_attempts=3))


def test_unknown_model_short_name_is_rejected() -> None:
    bad = base_config()
    bad["policies"][1]["write"] = "tiny"
    with pytest.raises(ValidationError, match="unknown model"):
        RunConfig.model_validate(bad)


def test_baseline_must_be_a_defined_policy() -> None:
    with pytest.raises(ValidationError, match="Baseline"):
        RunConfig.model_validate(base_config(baseline="missing"))


def test_policy_names_must_be_unique() -> None:
    bad = base_config()
    bad["policies"][1]["name"] = "big_only"
    with pytest.raises(ValidationError, match="unique"):
        RunConfig.model_validate(bad)


def test_unknown_effort_is_rejected() -> None:
    with pytest.raises(ValidationError):
        RunConfig.model_validate(base_config(effort="extreme"))


def test_unpriced_model_fails_before_a_run(prices: PriceTable) -> None:
    config = RunConfig.model_validate(base_config(models={"big": "x-1", "small": "x-2"}))
    with pytest.raises(PricingError):
        config.check_priced(prices)
