from __future__ import annotations

from pathlib import Path

import pytest

from aca.policies import RunConfig, load_run_config
from aca.pricing import PriceTable, load_prices

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def prices() -> PriceTable:
    return load_prices(REPO_ROOT / "config" / "prices.yaml")


@pytest.fixture(scope="session")
def config() -> RunConfig:
    return load_run_config(REPO_ROOT / "config" / "run.yaml")
