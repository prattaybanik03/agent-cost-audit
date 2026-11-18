# agent-cost-audit

A small, reproducible benchmark: on the same multi-agent coding workload, how much do model routing and prompt caching save, and does quality hold?

**Status: work in progress.** No results are published yet. Numbers will appear here only after a full run, and every figure will come from a file in `results/`.

## Run the tests

```
uv sync
uv run pytest
```

The tests use a mock provider. They need no API key and make no network calls.
