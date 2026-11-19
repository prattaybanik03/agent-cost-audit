# Method

How the benchmark works, in full. The [README](../README.md) has the short version, and [decisions.md](decisions.md) has the reasons behind each choice.

## Workload

Ten self-contained Python tasks in [`tasks/`](../tasks): 3 easy, 4 medium and 3 hard.

| Tier | Tasks |
| --- | --- |
| Easy | interval merging, LRU cache, Roman numerals with strict validation |
| Medium | token-bucket rate limiter, CSV validator with typed errors, tokenizer for a small expression language, semantic versions and ranges |
| Hard | expression parser and evaluator, next run time for a cron expression, spreadsheet with formulas and cycle detection |

Each task has a written specification (`prompt.md`), a hidden pytest file (`test_task.py`, 15 to 138 tests) and a reference solution (`reference.py`). The tests were written first. Every behaviour a test checks is stated in the specification, so a failure means the model got it wrong, not that the specification was vague.

The model sees only `prompt.md`. The `Task` object the run path uses has no field for the reference solution, and a test pins that.

Three checks keep the hidden tests honest:

- `aca tasks-verify` runs every reference solution (it must pass) and an empty solution (it must fail).
- [`tests/test_task_strength.py`](../tests/test_task_strength.py) plants 16 subtle bugs in the reference solutions, one at a time, and the hidden tests must catch each one.
- The same file checks all 51 expected dates in the cron task against a brute-force oracle that steps one minute at a time and shares no code with the reference solution.

## The agent loop

The same loop for every policy:

1. **Plan.** Read the specification and write a short plan.
2. **Write.** Write the module from the specification and the plan.
3. **Test.** Run the hidden tests in the sandbox.
4. **Fix.** On failure, send the code and the test output back. At most 2 fix attempts.

Every call uses the same shared system prompt of about 1,850 tokens: role, coding conventions and a description of the pipeline's tools. It clears the provider's 512-token minimum for caching. Each call is stateless: the loop passes forward only text, so any step can go to a different model.

Every call uses effort `medium` and an output allowance of 64,000 tokens, thinking included. Calls are streamed.

## Policies

| Policy | Plan | Write | Fix 1 | Fix 2 | System prompt cached |
| --- | --- | --- | --- | --- | --- |
| `opus` (baseline) | Opus 5.5 | Opus 5.5 | Opus 5.5 | Opus 5.5 | no |
| `sonnet` | Sonnet 5.5 | Sonnet 5.5 | Sonnet 5.5 | Sonnet 5.5 | no |
| `haiku` | Haiku 5.5 | Haiku 5.5 | Haiku 5.5 | Haiku 5.5 | no |
| `routed` | Opus 5.5 | Haiku 5.5 | Haiku 5.5 | Opus 5.5 | no |
| `*_cached` | as above | | | | yes |

Model IDs: `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-5-5`. Policies are data in [`config/run.yaml`](../config/run.yaml).

Each `_cached` policy differs from its pair only by `cache_control` on the system prompt, which separates the effect of caching from the effect of routing.

The system prompt starts with a one-line label naming the policy and the run. So two policies that use the same model never share a cache entry, and every run starts from a cold cache.

An earlier full run lacked the run ID in the label. It started within five minutes of earlier attempts, and three of its four cached policies began warm, logging no cache writes at all. It was discarded and the benchmark rerun from cold. The discarded run cost US$27.02 on top of the published run's US$26.62. Its conclusions were not materially different: caching then showed savings of 5% to 14%, against 11% to 12% from cold.

## Cost

Cost is computed per call from the token counts in the API's usage fields, never estimated. Cache writes and cache reads are priced at their own published rates.

US$ per million tokens, from <https://platform.claude.com/docs/en/about-claude/pricing>, checked 19 November 2026:

| Model | Input | Cache write (5 min) | Cache read | Output |
| --- | ---: | ---: | ---: | ---: |
| Claude Opus 5.5 | 4.00 | 5.00 | 0.20 | 20.00 |
| Claude Sonnet 5.5 | 2.00 | 2.50 | 0.10 | 10.00 |
| Claude Haiku 5.5 | 0.10 | 0.125 | 0.01 | 0.50 |

The table lives in [`config/prices.yaml`](../config/prices.yaml). A model or prompt size the table does not cover is an error, not a guess.

A hard budget cap is set in `config/run.yaml`. Before every call, the runner reserves that call's worst-case cost: the full output allowance, plus the prompt at the dearest rate. If the reservation could take spend past the cap, the call is not made and the run stops cleanly. A call that comes back from a model the table does not price is counted at its worst case, and the run stops.

## Sandbox

Generated code is untrusted. Each test run happens in a fresh Docker container with:

- no network (`--network none`);
- a read-only file system and no Linux capabilities;
- a non-root user;
- limits on memory, CPU, processes and time.

The base image is pinned by digest.

[`tests/test_sandbox.py`](../tests/test_sandbox.py) checks the isolation rather than assuming it. Inside the container, a socket connection must fail, file writes must fail and API keys must not be visible.

A task passes only if pytest exits 0 and its summary reports passed tests, no failures and no skipped tests. The exit code alone is not trusted, because generated code could end the process early with status 0 or skip the tests it would fail.

Without Docker, a subprocess fallback runs with a timeout and a stripped environment. It does not block network access, and it does not isolate the file system: generated code runs as you and can read any file you can, including `.env`. Use it only on a machine with no real secrets. All published results used the Docker sandbox.

## What is logged

`results/raw/<run_id>/calls.jsonl` holds one line per model call. Each line records:

- the run, task, policy, repetition, attempt and step;
- the provider and the model that served the call;
- input, output, cache-write and cache-read tokens;
- latency, cost, stop reason and timestamp.

It holds no prompt or response text.

`task_runs.jsonl` holds one line per task run. `run_meta.json` records the settings, the price table, the commit and whether the working tree had uncommitted changes. Generated code and test output go to `artifacts/`. `results/raw/` is not committed.

`aca report` turns one run's raw logs into [`results/summary.csv`](../results/summary.csv), [`results/report.md`](../results/report.md), [`results/chart.png`](../results/chart.png) and the README's results tables. No figure is typed by hand.
