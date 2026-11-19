| Policy | Cost per run of all 10 tasks | vs Opus | Passed | First try (95% interval) |
| --- | ---: | ---: | ---: | ---: |
| `opus` | $1.45 | baseline | 50/50 | 94% (84% to 98%) |
| `opus_cached` | $1.28 | -12% | 50/50 | 94% (84% to 98%) |
| `routed` | $0.72 | -51% | 50/50 | 90% (79% to 96%) |
| `routed_cached` | $0.64 | -56% | 50/50 | 92% (81% to 97%) |
| `sonnet` | $0.60 | -59% | 50/50 | 94% (84% to 98%) |
| `sonnet_cached` | $0.53 | -64% | 50/50 | 96% (87% to 99%) |
| `haiku` | $0.0557 | -96% | 50/50 | 90% (79% to 96%) |
| `haiku_cached` | $0.0491 | -97% | 50/50 | 94% (84% to 98%) |

**What caching added on its own** (same models, same steps, only `cache_control` differs), and how much of each policy's spend was output tokens, which caching cannot reduce:

| Models | Saving from caching | Range over repetitions | Cache writes | Output share of spend |
| --- | ---: | ---: | ---: | ---: |
| `opus` | -12% | -24% to -1% | 2 | 77% |
| `sonnet` | -11% | -17% to +3% | 1 | 73% |
| `haiku` | -12% | -17% to -7% | 1 | 85% |
| `routed` | -11% | -13% to -9% | 2 | 83% |
