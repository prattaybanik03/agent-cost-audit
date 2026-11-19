# Results

Run `20261118T232926Z`, started 2026-11-18T23:29:26.380200+00:00 and finished 2026-11-19T00:00:06.947505+00:00. Code at commit `01eb401`.

- Provider: anthropic. Token counts from API usage fields.
- 10 tasks × 8 policies × 5 repetitions. 400 of 400 task runs completed.
- Total API spend for this run: $27.02 (cap $75.00).
- Effort `medium` on every call. Output allowance 64,000 tokens per call. Up to 2 fix attempts per task.
- Sandbox: docker (network blocked).
- Prices from https://platform.claude.com/docs/en/about-claude/pricing, checked 2026-11-19.

### Headline: cost and quality by policy

Workload cost is the mean cost of each task, summed over all 10 tasks. The range is the cheapest and dearest full repetition. Change is against `opus`. Pass rate is over every task run. First-try rate is the share of task runs that passed with no fix attempt.

| Policy | Workload cost | Range over reps | Cost vs baseline | Pass rate | First-try rate | Fix attempts | Cost per passed task |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `opus` | $1.46 | $1.37 – $1.56 | baseline | 100% | 94% | 3 | $0.15 |
| `opus_cached` | $1.33 | $1.23 – $1.39 | -9% | 100% | 92% | 4 | $0.13 |
| `routed` | $0.74 | $0.70 – $0.77 | -50% | 100% | 94% | 3 | $0.0739 |
| `routed_cached` | $0.64 | $0.60 – $0.66 | -57% | 100% | 94% | 3 | $0.0635 |
| `sonnet` | $0.60 | $0.57 – $0.65 | -59% | 100% | 94% | 3 | $0.0598 |
| `sonnet_cached` | $0.53 | $0.51 – $0.59 | -64% | 100% | 92% | 4 | $0.0534 |
| `haiku` | $0.0529 | $0.0485 – $0.0552 | -96% | 100% | 94% | 3 | $0.0053 |
| `haiku_cached` | $0.0504 | $0.0478 – $0.0538 | -97% | 100% | 84% | 8 | $0.0050 |


### Caching on its own

Each pair runs the same models on the same steps. The only difference is `cache_control` on the shared system prompt. Cache-read share is the fraction of prompt tokens served from the cache.

| Models | Uncached | Cached | Change | Cache-read share | Pass rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| `opus` | $1.46 | $1.33 | -9% | 48% | 100% → 100% |
| `sonnet` | $0.60 | $0.53 | -11% | 49% | 100% → 100% |
| `haiku` | $0.0529 | $0.0504 | -5% | 50% | 100% → 100% |
| `routed` | $0.74 | $0.64 | -14% | 48% | 100% → 100% |


### Where the money goes

Share of each policy's spend by step, and the share that paid for output tokens (thinking included). Prompt caching can only reduce the rest.

| Policy | Plan | Write | Fix | Output tokens |
| --- | ---: | ---: | ---: | ---: |
| `opus` | 47% | 48% | 5% | 77% |
| `opus_cached` | 47% | 46% | 8% | 85% |
| `sonnet` | 40% | 56% | 4% | 73% |
| `sonnet_cached` | 38% | 57% | 5% | 83% |
| `haiku` | 33% | 63% | 4% | 85% |
| `haiku_cached` | 30% | 63% | 7% | 90% |
| `routed` | 95% | 5% | 0% | 83% |
| `routed_cached` | 95% | 5% | 0% | 92% |


### Where the cheaper route lost

Every task where a policy cost more than `opus` on average, or passed less often. The reasons are read from the call logs.

| Task | Policy | Lost on | Cost | Pass rate | Why |
| --- | --- | --- | ---: | ---: | --- |
| `h3_spreadsheet` | `opus_cached` | cost | $0.4249 vs $0.4243 (+0.1%) | 100% vs 100% | 0.8 fix attempts per run vs 0.6 |


### Latency

Call latency is the time from sending a request to receiving the full streamed reply. Task time includes every call and every test run for that task.

| Policy | Call p50 | Call p95 | Mean task time | Escalations | Output-limit stops |
| --- | ---: | ---: | ---: | ---: | ---: |
| `opus` | 20.4 s | 62.8 s | 52 s | 0 | 0 |
| `opus_cached` | 20.4 s | 63.2 s | 51 s | 0 | 0 |
| `sonnet` | 11.5 s | 37.0 s | 31 s | 0 | 0 |
| `sonnet_cached` | 11.4 s | 31.8 s | 31 s | 0 | 0 |
| `haiku` | 12.0 s | 50.8 s | 39 s | 0 | 0 |
| `haiku_cached` | 11.6 s | 52.0 s | 40 s | 0 | 0 |
| `routed` | 19.2 s | 72.6 s | 54 s | 0 | 0 |
| `routed_cached` | 15.8 s | 63.2 s | 50 s | 0 | 0 |


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
