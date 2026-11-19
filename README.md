# agent-cost-audit

A small, reproducible benchmark of AI spend control on a multi-agent coding workload: how much do model routing and prompt caching save, and does quality hold?

<!-- headline:start -->
**Result, 400 task runs, US$26.62 in API spend:** on this workload every policy passed every task. Running everything on Haiku 5.5 cut cost by 96% against Opus 5.5. Routing (Opus plans, Haiku writes) cut it by 51%. Caching the system prompt saved a further 11% to 12% in every pairing. The cheap route lost only when its output allowance was too small: at 16,000 tokens, Haiku was cut off mid-answer and failed the hardest task, and the cached routed policy then cost more than cached Opus.
<!-- headline:end -->

![Cost per task by policy, with pass rate](results/chart.png)

## The question

Coding agents make many model calls per task: plan, write, test, fix. Two common ways to cut their bill are:

- **Routing.** Send the expensive steps to a strong model and the routine ones to a cheap model.
- **Prompt caching.** Mark the long shared prefix (the system prompt) so repeat calls read it from cache at a fraction of the input price.

Both are sold as savings. This repo measures them on one workload, with real API calls, and counts the cases where the cheaper route ends up costing more or failing.

It is a benchmark and a report, not a product.

## Quick start

Needs Python 3.11+, [uv](https://docs.astral.sh/uv/) and, for the network-isolated sandbox, Docker.

```
uv sync
uv run aca sandbox-build          # builds the test sandbox image (optional; falls back to a subprocess)
uv run pytest                     # unit tests; mock provider only, no API key
```

Reproduce the whole pipeline with the mock provider. No API key, no spend. Token counts are estimates, so the numbers mean nothing; it shows the run, the logs and the report work end to end:

```
uv run aca run --provider mock --reps 1
uv run aca report results/raw/<run_id> --out results/raw/mock-report
```

A real run. Copy `.env.example` to `.env` and add an Anthropic API key first:

```
uv run aca run                    # 10 tasks x 8 policies x 5 repetitions, hard cap in config/run.yaml
uv run aca report results/raw/<run_id> --readme README.md
```

`aca run --tasks e1_interval_merge --policies opus,haiku --reps 1 --cap 1` runs a slice.

## Method

### Workload

Ten self-contained Python tasks in `tasks/`: 3 easy, 4 medium and 3 hard.

| Tier | Tasks |
| --- | --- |
| Easy | interval merging, LRU cache, Roman numerals with strict validation |
| Medium | token-bucket rate limiter, CSV validator with typed errors, tokenizer for a small expression language, semantic versions and ranges |
| Hard | expression parser and evaluator, next run time for a cron expression, spreadsheet with formulas and cycle detection |

Each task has a written specification (`prompt.md`), a hidden pytest file and a reference solution. The tests were written first. `aca tasks-verify` checks that every reference solution passes and an empty solution fails. A task passes only if every hidden test passes. The model never sees the tests or the reference solution.

### The agent loop

The same loop for every policy:

1. **Plan.** Read the specification and write a short plan.
2. **Write.** Write the module from the specification and the plan.
3. **Test.** Run the hidden tests in the sandbox.
4. **Fix.** On failure, send the code and the test output back. At most 2 fix attempts.

Every call uses the same shared system prompt of about 1,850 tokens (role, coding conventions, a description of the pipeline's tools). It clears the provider's 512-token minimum for caching. Each call is stateless: the loop passes forward only text, so any step can go to a different model.

Every call uses effort `medium` and an output allowance of 64,000 tokens, thinking included. Calls are streamed.

### Policies

| Policy | Plan | Write | Fix 1 | Fix 2 | System prompt cached |
| --- | --- | --- | --- | --- | --- |
| `opus` (baseline) | Opus 5.5 | Opus 5.5 | Opus 5.5 | Opus 5.5 | no |
| `sonnet` | Sonnet 5.5 | Sonnet 5.5 | Sonnet 5.5 | Sonnet 5.5 | no |
| `haiku` | Haiku 5.5 | Haiku 5.5 | Haiku 5.5 | Haiku 5.5 | no |
| `routed` | Opus 5.5 | Haiku 5.5 | Haiku 5.5 | Opus 5.5 | no |
| `*_cached` | as above | | | | yes |

Each `_cached` policy differs from its pair only by `cache_control` on the system prompt. That separates the effect of caching from the effect of routing. The system prompt starts with a one-line label naming the policy and the run, so two policies that use the same model never share a cache entry, and every run starts from a cold cache. An earlier full run lacked the run ID in the label. It started within five minutes of earlier attempts, and three of its four cached policies began warm, logging no cache writes at all. It was discarded and the benchmark rerun from cold. The discarded run cost US$27.02 on top of the published run's US$26.62, and its conclusions were not materially different: caching then showed savings of 5% to 14% against 11% to 12% from cold.

Model IDs: `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-5-5`.

### Cost

Cost is computed per call from the token counts in the API's usage fields, never estimated. Cache writes and cache reads are priced at their own published rates.

US$ per million tokens, from <https://platform.claude.com/docs/en/about-claude/pricing>, checked 19 November 2026:

| Model | Input | Cache write (5 min) | Cache read | Output |
| --- | ---: | ---: | ---: | ---: |
| Claude Opus 5.5 | 4.00 | 5.00 | 0.20 | 20.00 |
| Claude Sonnet 5.5 | 2.00 | 2.50 | 0.10 | 10.00 |
| Claude Haiku 5.5 | 0.10 | 0.125 | 0.01 | 0.50 |

The table lives in `config/prices.yaml`. A model or prompt size the table does not cover is an error, not a guess.

A hard budget cap is set in `config/run.yaml`. Before every call the runner reserves that call's worst-case cost (the full output allowance, the prompt at the dearest rate). If the reservation could pass the cap, the call is not made and the run stops cleanly.

### Sandbox

Generated code is untrusted. Each test run happens in a fresh Docker container with no network (`--network none`), a read-only file system, no Linux capabilities, a non-root user, and limits on memory, CPU, processes and time. Tests in `tests/test_sandbox.py` check that a socket connection fails, file writes fail and API keys are not visible inside. Without Docker, a subprocess fallback runs with a timeout and a stripped environment. It does not block network access, and it does not isolate the file system: generated code runs as you and can read any file you can, including `.env`. Use it only on a machine with no real secrets. All published results used the Docker sandbox.

A task passes only if pytest exits 0 and its summary reports passed tests and no failures. The exit code alone is not trusted, because generated code could end the process early with status 0.

### What is logged

`results/raw/<run_id>/calls.jsonl` holds one line per model call: run, task, policy, repetition, attempt, step, provider, the model that served the call, input, output, cache-write and cache-read tokens, latency, cost, stop reason and timestamp. It holds no prompt or response text. Generated code and test output go to `artifacts/` in the same folder. `results/raw/` is not committed.

## Results

<!-- results:start -->

### Headline: cost and quality by policy

Workload cost is the mean cost of each task, summed over all 10 tasks. The range is the cheapest and dearest full repetition. Change is against `opus`. Pass rate is over every task run. First-try rate is the share of task runs that passed with no fix attempt, with its 95% Wilson interval: two policies whose intervals overlap are not shown to differ by this run.

| Policy | Workload cost | Range over reps | Cost vs baseline | Pass rate | First-try rate | Fix attempts | Cost per passed task |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `opus` | $1.45 | $1.33 to $1.57 | baseline | 100% | 94% (84% to 98%) | 3 | $0.15 |
| `opus_cached` | $1.28 | $1.19 to $1.36 | -12% | 100% | 94% (84% to 98%) | 3 | $0.13 |
| `routed` | $0.72 | $0.69 to $0.73 | -51% | 100% | 90% (79% to 96%) | 5 | $0.0718 |
| `routed_cached` | $0.64 | $0.62 to $0.66 | -56% | 100% | 92% (81% to 97%) | 4 | $0.0640 |
| `sonnet` | $0.60 | $0.57 to $0.62 | -59% | 100% | 94% (84% to 98%) | 3 | $0.0596 |
| `sonnet_cached` | $0.53 | $0.50 to $0.59 | -64% | 100% | 96% (87% to 99%) | 2 | $0.0529 |
| `haiku` | $0.0557 | $0.0509 to $0.0600 | -96% | 100% | 90% (79% to 96%) | 5 | $0.0056 |
| `haiku_cached` | $0.0491 | $0.0442 to $0.0518 | -97% | 100% | 94% (84% to 98%) | 4 | $0.0049 |


### Caching on its own

Each pair runs the same models on the same steps. The only difference is `cache_control` on the shared system prompt. Rep range compares repetition k of each; repetitions are independent, so it shows spread, not a paired effect. Cache writes counts the calls that paid the write premium. Cache-read share is the fraction of prompt tokens served from the cache.

| Models | Uncached | Cached | Change | Rep range | Cache writes | Cache-read share | Pass rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `opus` | $1.45 | $1.28 | -12% | -24% to -1% | 2 (3,700 tokens) | 47% | 100% → 100% |
| `sonnet` | $0.60 | $0.53 | -11% | -17% to +3% | 1 (1,852 tokens) | 49% | 100% → 100% |
| `haiku` | $0.0557 | $0.0491 | -12% | -17% to -7% | 1 (1,851 tokens) | 50% | 100% → 100% |
| `routed` | $0.72 | $0.64 | -11% | -13% to -9% | 2 (3,700 tokens) | 47% | 100% → 100% |


### Where the money goes

Share of each policy's spend by step, and the share that paid for output tokens (thinking included). Prompt caching can only reduce the rest.

| Policy | Plan | Write | Fix | Output tokens |
| --- | ---: | ---: | ---: | ---: |
| `opus` | 47% | 48% | 6% | 77% |
| `opus_cached` | 47% | 47% | 6% | 85% |
| `sonnet` | 38% | 59% | 3% | 73% |
| `sonnet_cached` | 38% | 60% | 2% | 83% |
| `haiku` | 31% | 62% | 7% | 85% |
| `haiku_cached` | 29% | 65% | 6% | 90% |
| `routed` | 95% | 5% | 0% | 83% |
| `routed_cached` | 95% | 5% | 0% | 91% |


### Where the cheaper route lost

No policy cost more than `opus` or passed less often on any task.


### Latency

Call latency is the time from sending a request to receiving the full streamed reply. Task time includes every call and every test run for that task.

| Policy | Call p50 | Call p95 | Mean task time | Escalations | Output-limit stops |
| --- | ---: | ---: | ---: | ---: | ---: |
| `opus` | 19.5 s | 66.0 s | 52 s | 0 | 0 |
| `opus_cached` | 19.8 s | 62.0 s | 51 s | 0 | 0 |
| `sonnet` | 11.6 s | 32.0 s | 32 s | 0 | 0 |
| `sonnet_cached` | 10.3 s | 29.7 s | 32 s | 0 | 0 |
| `haiku` | 12.5 s | 54.8 s | 42 s | 0 | 0 |
| `haiku_cached` | 11.1 s | 43.0 s | 40 s | 0 | 0 |
| `routed` | 18.0 s | 76.5 s | 54 s | 0 | 0 |
| `routed_cached` | 18.3 s | 69.8 s | 52 s | 0 | 0 |


### Pass rate by task

| Task | `opus` | `opus_cached` | `sonnet` | `sonnet_cached` | `haiku` | `haiku_cached` | `routed` | `routed_cached` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `e1_interval_merge` (easy) | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| `e2_lru_cache` (easy) | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| `e3_roman_numerals` (easy) | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| `m1_rate_limiter` (medium) | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| `m2_csv_validator` (medium) | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| `m3_tokenizer` (medium) | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| `m4_semver` (medium) | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| `h1_expr_eval` (hard) | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| `h2_cron_next` (hard) | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| `h3_spreadsheet` (hard) | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |

<!-- results:end -->

The full per-task table is in [`results/summary.csv`](results/summary.csv) and the report in [`results/report.md`](results/report.md).

### What the numbers say

- **The cheapest model was enough here.** Haiku 5.5 passed all 50 of its task runs, 90% of them on the first try, against 94% for Opus 5.5. The 95% intervals overlap (79% to 96% and 84% to 98%), so this run does not show a quality difference. These ten tasks did not need a frontier model when the specification was precise.
- **Routing paid for a step that bought nothing measurable.** In `routed`, 95% of the spend went on the Opus planning step. Haiku's code passed before the second fix in every run, so the policy never escalated. It cost about 13 times as much as Haiku alone for the same pass rate.
- **Caching saved less than its headline rate suggests.** A cache read costs 5% of the input price on Opus and Sonnet and 10% on Haiku. But output tokens, thinking included, were 73% to 91% of every policy's spend, and caching does not touch them. Caching the roughly 1,850-token system prompt cut total cost by 11% to 12% in every pairing. Repetition by repetition the saving ranged from 1% to 24% for Opus, and the Sonnet pair had one repetition where the cached policy cost 3% more.
- **The write premium hardly registered.** Each cached policy started from a cold cache and paid for one or two cache writes in about 100 calls. `opus_cached` wrote twice because two tasks started within two seconds of each other, before either write could be read. `routed_cached` wrote twice because caches are per model and it uses two models. Calls arrived seconds apart, well inside the 5-minute cache lifetime. A workload with longer gaps between calls would pay the write premium more often.
- **Haiku was not the fastest.** Its median call was close to Sonnet's (12.5 s against 11.6 s), but its slowest calls were slower (p95 54.8 s against 32.0 s). On the hard tasks it produced more output tokens per call, thinking included.

### When the cheap route did lose

In the full run, no policy cost more than `opus` or passed less often on any task.

The cheap route did lose in the [smoke test](results/smoke-16k-limit/report.md), run with an output allowance of 16,000 tokens (2 tasks x 8 policies x 1 repetition, US$2.24, n = 1, so read it as a case, not a rate). On the spreadsheet task, every Haiku write and fix hit the limit, so its code was cut off mid-reply. `haiku` and `haiku_cached` failed it outright. `routed` and `routed_cached` escalated to Opus on the last fix and still failed 2 of 115 tests.

Compared like for like, `routed_cached` spent $0.36 on that task against $0.32 for `opus_cached`, which passed: **12% more, for a failure.** `routed` spent 88% of what `opus` spent and also failed. Opus's largest reply in the smoke test used 13,368 tokens, 84% of the limit, so a harder task could have cut off the expensive model too.

Raising the allowance to 64,000 tokens fixed it. The lesson for anyone routing to a cheap model: a per-call output cap set for the expensive model can quietly make the cheap one fail, and the failure looks like poor quality, not a configuration problem.

## Limitations

- **The tasks are too easy to separate the models on pass rate.** Every policy passed every task, so pass rate shows no difference. First-try rate and fix attempts show a little. A harder task set would test whether quality really holds.
- **Small n.** Each task x policy ran 5 times, 50 task runs per policy. The tables give the range over repetitions and 95% intervals on first-try rates. Differences smaller than those spreads are not shown by this run.
- **Prices as of one date.** Prices were checked on 19 November 2026 and will change. Re-check `config/prices.yaml` before relying on any dollar figure.
- **Synthetic tasks.** Ten self-contained tasks are not a real codebase. Real agents read files, call tools and carry long histories, which makes the cached prefix larger and caching worth more than here.
- **One loop shape.** Results depend on the loop: two fix attempts, stateless calls and one escalation rule. A different harness would give different numbers.
- **One provider, one effort setting.** All models ran at effort `medium`. Effort is itself a cost lever this benchmark does not vary.
- **Public reference solutions.** The reference solutions are in this repo. They never enter a prompt, but a future model trained on public code could have seen them.
- **Hardware not costed.** Only API spend is counted, not the machine that ran the sandbox.

## What I'd do next

- **A budget-aware router.** The routed policy escalates only after a failed cheap fix. A router that predicts from the task and the first test output when escalation is likely could skip the wasted cheap attempts.
- **Run it on real agent logs.** An `aca ingest` command that reads call logs in the same schema and produces the same report. The first target is a multi-agent system from a university team project, through a small logging wrapper added there with the team's agreement. Only aggregated numbers would come into this repo.
- **A small open model in the routing ladder,** served on rented GPUs, to see whether self-hosting the cheap step changes the picture.

## How this was built

I built this as the engineer in charge, directing AI coding agents the way a lead directs a team.

- **I framed the problem and the business case.** I chose the question an AI spend-control product has to answer for a buyer, what result would be credible, and what the benchmark must not claim.
- **I made the product and architecture decisions.** I chose the policy matrix, comparing all three model tiers with routing and caching twins, and set Opus as the baseline. I chose Anthropic models only for v1, the one provider interface, the hard budget cap with worst-case reservation, the Docker sandbox, the call-log schema and the rule that every published number comes from a logged run.
- **I directed the work in stages.** I gave the agents a specification and acceptance criteria for each stage, reviewed what came back, and approved each stage before the next began.
- **I verified it.** I ran the checks below, read the call logs behind the headline numbers, and had an independent agent, which had not seen the work, review the repository against my engineering standards before release.
- **I changed the design when the evidence said so.** A smoke test showed the cheap model cut off at a 16,000-token output limit, so I raised the allowance to 64,000. I turned off refusal fallback so no call could be served by a model other than the one under test. The independent review found that the first full run's cached policies had started on a warm cache. I fixed the cache isolation and reran the benchmark from cold rather than publish a caveated result.
- **I shipped it.** I set the release gate, chose the licence and approved the release.

The checks that back the numbers are all in `tests/` and need no API key. The CI workflow runs them on every push:

- a reference solution that must pass and an empty solution that must fail for every task;
- 16 planted bugs the hidden tests must catch (`tests/test_task_strength.py`);
- a brute-force cross-check of all 51 expected dates in the cron task;
- sandbox tests showing no network, no file writes, no visible API key, and no pass for code that exits early or skips tests;
- the budget cap, pricing and cache accounting.

213 tests in all, plus lint and type checks. CI actions are pinned to commit SHAs and the sandbox image to a digest. A dependency audit of the 45 locked packages found no known vulnerabilities on 19 November 2026.
