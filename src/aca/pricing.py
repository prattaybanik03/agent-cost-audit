"""Prices come from config/prices.yaml, which records the source URL and the date checked.

Nothing here guesses a price. An unknown model, or a prompt outside the priced tier, is an error.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from aca.providers.base import Usage

PER_MTOK = 1_000_000


class PricingError(Exception):
    """Raised when a call cannot be priced from the published table."""


class ModelPrice(BaseModel):
    """US dollars per million tokens."""

    input: float = Field(ge=0)
    output: float = Field(ge=0)
    cache_write_5m: float = Field(ge=0)
    cache_write_1h: float = Field(ge=0)
    cache_read: float = Field(ge=0)
    max_prompt_tokens: int | None = None
    """These prices apply only to prompts up to this size. None means no stated limit."""


class PriceTable(BaseModel):
    source_url: str
    date_checked: date
    currency: str
    models: dict[str, ModelPrice]

    def price_for(self, model: str) -> ModelPrice:
        try:
            return self.models[model]
        except KeyError:
            raise PricingError(
                f"No price for model {model!r} in the price table. "
                "Add it to config/prices.yaml from the provider's pricing page."
            ) from None

    def cost_usd(self, model: str, usage: Usage) -> float:
        """Cost of one call, from the token counts the provider reported."""
        price = self.price_for(model)
        self._check_tier(model, price, usage.prompt_tokens)
        total = (
            usage.input_tokens * price.input
            + usage.output_tokens * price.output
            + usage.cache_write_5m_tokens * price.cache_write_5m
            + usage.cache_write_1h_tokens * price.cache_write_1h
            + usage.cache_read_tokens * price.cache_read
        )
        return total / PER_MTOK

    def worst_case_usd(self, model: str, prompt_tokens: int, max_output_tokens: int) -> float:
        """Upper bound for a call that has not happened yet. Used only for the budget check.

        Prices the whole prompt at the dearest prompt rate and assumes the full output allowance.
        """
        price = self.price_for(model)
        self._check_tier(model, price, prompt_tokens)
        prompt_rate = max(price.input, price.cache_write_5m, price.cache_write_1h)
        return (prompt_tokens * prompt_rate + max_output_tokens * price.output) / PER_MTOK

    @staticmethod
    def _check_tier(model: str, price: ModelPrice, prompt_tokens: int) -> None:
        if price.max_prompt_tokens is not None and prompt_tokens > price.max_prompt_tokens:
            raise PricingError(
                f"{model} prompt of {prompt_tokens} tokens exceeds the {price.max_prompt_tokens}"
                "-token tier these prices cover. Add the long-context prices before pricing it."
            )


def load_prices(path: str | Path) -> PriceTable:
    with open(path, encoding="utf-8") as handle:
        return PriceTable.model_validate(yaml.safe_load(handle))
