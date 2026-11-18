"""Policies decide which model handles each step. They are data, loaded from config/run.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

from aca.pricing import PriceTable

Effort = Literal["low", "medium", "high", "xhigh", "max"]


class Policy(BaseModel):
    """Model short names for each step. Resolved to model IDs through `RunConfig.models`."""

    name: str
    plan: str
    write: str
    fix: list[str]
    cache: bool = False

    def steps(self) -> list[str]:
        return [self.plan, self.write, *self.fix]


class RunConfig(BaseModel):
    budget_cap_usd: float = Field(gt=0)
    repetitions: int = Field(ge=1)
    max_fix_attempts: int = Field(ge=0)
    max_tokens: int = Field(ge=1)
    effort: Effort
    models: dict[str, str]
    baseline: str
    policies: list[Policy]

    @model_validator(mode="after")
    def _check(self) -> RunConfig:
        names = [p.name for p in self.policies]
        if len(names) != len(set(names)):
            raise ValueError("Policy names must be unique.")
        if self.baseline not in names:
            raise ValueError(f"Baseline policy {self.baseline!r} is not defined.")
        for policy in self.policies:
            if len(policy.fix) != self.max_fix_attempts:
                raise ValueError(
                    f"Policy {policy.name!r} lists {len(policy.fix)} fix models "
                    f"but max_fix_attempts is {self.max_fix_attempts}."
                )
            for short in policy.steps():
                if short not in self.models:
                    raise ValueError(f"Policy {policy.name!r} uses unknown model {short!r}.")
        return self

    def model_id(self, short: str) -> str:
        return self.models[short]

    def policy(self, name: str) -> Policy:
        for policy in self.policies:
            if policy.name == name:
                return policy
        raise KeyError(f"No policy named {name!r}.")

    def check_priced(self, prices: PriceTable) -> None:
        """Fail before the run starts if any model a policy uses has no published price."""
        for model_id in sorted(set(self.models.values())):
            prices.price_for(model_id)


def load_run_config(path: str | Path) -> RunConfig:
    with open(path, encoding="utf-8") as handle:
        return RunConfig.model_validate(yaml.safe_load(handle))
