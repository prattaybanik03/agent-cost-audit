from __future__ import annotations

import pytest

from aca.pricing import PriceTable, PricingError
from aca.providers.base import Usage

OPUS = "claude-opus-5-5"
SONNET = "claude-sonnet-5-5"
HAIKU = "claude-haiku-5-5"


def test_price_table_records_its_source(prices: PriceTable) -> None:
    assert prices.source_url.startswith("https://")
    assert prices.date_checked.year >= 2026
    assert prices.currency == "USD"


def test_plain_call_cost(prices: PriceTable) -> None:
    usage = Usage(input_tokens=1000, output_tokens=500)
    # 1000 x $2/M + 500 x $10/M
    assert prices.cost_usd(SONNET, usage) == pytest.approx(0.007)


def test_cache_writes_and_reads_use_their_own_rates(prices: PriceTable) -> None:
    write_5m = Usage(cache_write_5m_tokens=4000)
    write_1h = Usage(cache_write_1h_tokens=4000)
    read = Usage(cache_read_tokens=4000)
    assert prices.cost_usd(OPUS, write_5m) == pytest.approx(0.020)
    assert prices.cost_usd(OPUS, write_1h) == pytest.approx(0.032)
    assert prices.cost_usd(OPUS, read) == pytest.approx(0.0008)


def test_mixed_call_sums_every_category(prices: PriceTable) -> None:
    usage = Usage(input_tokens=200, output_tokens=300, cache_read_tokens=3000)
    expected = (200 * 0.10 + 300 * 0.50 + 3000 * 0.01) / 1_000_000
    assert prices.cost_usd(HAIKU, usage) == pytest.approx(expected)


def test_unknown_model_is_an_error_not_a_guess(prices: PriceTable) -> None:
    with pytest.raises(PricingError, match="No price for model"):
        prices.cost_usd("some-other-model", Usage(input_tokens=1))


def test_prompt_beyond_the_priced_tier_is_an_error(prices: PriceTable) -> None:
    with pytest.raises(PricingError, match="exceeds"):
        prices.cost_usd(HAIKU, Usage(input_tokens=100_001))
    # Exactly at the limit is still priced.
    assert prices.cost_usd(HAIKU, Usage(input_tokens=100_000)) == pytest.approx(0.01)


def test_worst_case_uses_dearest_prompt_rate_and_full_output(prices: PriceTable) -> None:
    # Opus: dearest prompt rate is the 1-hour cache write at $8/M; output $20/M.
    assert prices.worst_case_usd(OPUS, 1000, 2000) == pytest.approx(0.048)


@pytest.mark.parametrize("model", [OPUS, SONNET, HAIKU])
def test_worst_case_is_never_below_actual(prices: PriceTable, model: str) -> None:
    usage = Usage(input_tokens=500, output_tokens=800, cache_write_5m_tokens=3000)
    worst = prices.worst_case_usd(model, usage.prompt_tokens, 800)
    assert worst >= prices.cost_usd(model, usage)


@pytest.mark.parametrize("model", [OPUS, SONNET, HAIKU])
def test_config_matches_published_cache_multipliers(prices: PriceTable, model: str) -> None:
    """Guards against typos: the pricing page states writes are 1.25x and 2x the input price."""
    price = prices.price_for(model)
    assert price.cache_write_5m == pytest.approx(price.input * 1.25)
    assert price.cache_write_1h == pytest.approx(price.input * 2)
    assert price.cache_read < price.input
