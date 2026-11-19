# Results

Run `20261118T231252Z`, started 2026-11-18T23:12:52.103365+00:00 and finished 2026-11-18T23:20:22.707692+00:00. Code at commit `f9632e3`.

- Provider: anthropic. Token counts from API usage fields.
- 2 tasks × 8 policies × 1 repetition. 16 of 16 task runs completed.
- Total API spend for this run: $2.24 (cap $5.00).
- Effort `medium` on every call. Output allowance 16,000 tokens per call. Up to 2 fix attempts per task.
- Sandbox: docker (network blocked).
- Prices from https://platform.claude.com/docs/en/about-claude/pricing, checked 2026-11-19.

### Headline: cost and quality by policy

Workload cost is the mean cost of each task, summed over all 2 tasks. The range is the cheapest and dearest full repetition. Change is against `opus`. Pass rate is over every task run. First-try rate is the share of task runs that passed with no fix attempt.

| Policy | Workload cost | Range over reps | Cost vs baseline | Pass rate | First-try rate | Fix attempts | Cost per passed task |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `opus` | $0.56 | $0.56 – $0.56 | baseline | 100% | 50% | 1 | $0.28 |
| `routed` | $0.48 | $0.48 – $0.48 | -14% | 50% | 50% | 2 | $0.48 |
| `routed_cached` | $0.39 | $0.39 – $0.39 | -29% | 50% | 50% | 2 | $0.39 |
| `opus_cached` | $0.37 | $0.37 – $0.37 | -33% | 100% | 100% | 0 | $0.19 |
| `sonnet_cached` | $0.19 | $0.19 – $0.19 | -65% | 100% | 100% | 0 | $0.0974 |
| `sonnet` | $0.19 | $0.19 – $0.19 | -66% | 100% | 100% | 0 | $0.0936 |
| `haiku_cached` | $0.0302 | $0.0302 – $0.0302 | -95% | 50% | 50% | 2 | $0.0302 |
| `haiku` | $0.0301 | $0.0301 – $0.0301 | -95% | 50% | 50% | 2 | $0.0301 |


### Caching on its own

Each pair runs the same models on the same steps. The only difference is `cache_control` on the shared system prompt. Cache-read share is the fraction of prompt tokens served from the cache.

| Models | Uncached | Cached | Change | Cache-read share | Pass rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| `opus` | $0.56 | $0.37 | -33% | 33% | 100% → 100% |
| `sonnet` | $0.19 | $0.19 | +4% | 32% | 100% → 100% |
| `haiku` | $0.0301 | $0.0302 | +1% | 37% | 50% → 50% |
| `routed` | $0.48 | $0.39 | -18% | 20% | 50% → 50% |


### Where the money goes

Share of each policy's spend by step, and the share that paid for output tokens (thinking included). Prompt caching can only reduce the rest.

| Policy | Plan | Write | Fix | Output tokens |
| --- | ---: | ---: | ---: | ---: |
| `opus` | 33% | 42% | 25% | 82% |
| `opus_cached` | 44% | 56% | 0% | 87% |
| `sonnet` | 28% | 72% | 0% | 83% |
| `sonnet_cached` | 30% | 70% | 0% | 87% |
| `haiku` | 13% | 31% | 56% | 92% |
| `haiku_cached` | 16% | 29% | 54% | 95% |
| `routed` | 37% | 2% | 61% | 91% |
| `routed_cached` | 41% | 2% | 57% | 92% |


### Where the cheaper route lost

Every task where a policy cost more than `opus` on average, or passed less often. The reasons are read from the call logs.

| Task | Policy | Lost on | Cost | Pass rate | Why |
| --- | --- | --- | ---: | ---: | --- |
| `h3_spreadsheet` | `haiku` | quality | $0.0287 vs $0.5023 (-94.3%) | 0% vs 100% | 3 replies cut off at the output limit; 2.0 fix attempts per run vs 1.0; 53,854 output tokens per run vs 21,243 |
| `h3_spreadsheet` | `haiku_cached` | quality | $0.0291 vs $0.5023 (-94.2%) | 0% vs 100% | 3 replies cut off at the output limit; 2.0 fix attempts per run vs 1.0; 55,932 output tokens per run vs 21,243 |
| `h3_spreadsheet` | `routed` | quality | $0.4415 vs $0.5023 (-12.1%) | 0% vs 100% | 2 replies cut off at the output limit; escalated to the strong model in 100% of runs; 2.0 fix attempts per run vs 1.0; 51,673 output tokens per run vs 21,243 |
| `h3_spreadsheet` | `routed_cached` | quality | $0.3574 vs $0.5023 (-28.8%) | 0% vs 100% | 2 replies cut off at the output limit; escalated to the strong model in 100% of runs; 2.0 fix attempts per run vs 1.0; 48,182 output tokens per run vs 21,243 |


### Latency

Call latency is the time from sending a request to receiving the full streamed reply. Task time includes every call and every test run for that task.

| Policy | Call p50 | Call p95 | Mean task time | Escalations | Output-limit stops |
| --- | ---: | ---: | ---: | ---: | ---: |
| `opus` | 35.7 s | 76.0 s | 100 s | 0 | 0 |
| `opus_cached` | 37.1 s | 71.1 s | 76 s | 0 | 0 |
| `sonnet` | 16.1 s | 67.8 s | 57 s | 0 | 0 |
| `sonnet_cached` | 20.0 s | 71.9 s | 62 s | 0 | 0 |
| `haiku` | 50.3 s | 74.8 s | 131 s | 0 | 3 |
| `haiku_cached` | 54.0 s | 72.8 s | 133 s | 0 | 3 |
| `routed` | 66.4 s | 109.7 s | 175 s | 1 | 2 |
| `routed_cached` | 62.5 s | 88.3 s | 156 s | 1 | 2 |


### Pass rate by task

| Task | `opus` | `opus_cached` | `sonnet` | `sonnet_cached` | `haiku` | `haiku_cached` | `routed` | `routed_cached` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `e1_interval_merge` (easy) | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| `h3_spreadsheet` (hard) | 100% | 100% | 100% | 100% | 0% | 0% | 0% | 0% |
