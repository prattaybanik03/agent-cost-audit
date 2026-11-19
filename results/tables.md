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
