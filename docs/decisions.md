# Decisions

The choices that shape the results, and what each one gives up. Each has a condition for revisiting it.

## D1. Anthropic models only for v1

- **Context.** The first plan routed to a local open model. On the build machine's integrated graphics, local inference would have taken hours per run and threatened the deadline.
- **Decision.** Compare Haiku 5.5, Sonnet 5.5 and Opus 5.5, all through one provider.
- **What we give up.** The self-hosted cheap step, and any claim about other providers.
- **Revisit when.** A small open model can be served on rented GPUs. The provider interface takes a new implementation without changes elsewhere.

## D2. Opus as the baseline, all three tiers as rows

- **Context.** A routing benchmark that only compares "expensive" and "routed" cannot tell whether the cheap model alone would have done.
- **Decision.** Every tier runs as its own policy, and routing is one more policy on top.
- **What we give up.** Run cost: eight policies instead of three.
- **Revisit when.** Never for this question. The single-model Haiku row produced the headline finding.

## D3. Effort pinned to `medium` for every call

- **Context.** Effort changes how much a model thinks, and thinking is billed as output.
- **Decision.** One effort setting for every model and policy, recorded with each run.
- **What we give up.** Effort as a cost lever, which may beat routing.
- **Revisit when.** The next version varies effort as its own policy dimension.

## D4. Output allowance of 64,000 tokens, streamed

- **Context.** At 16,000 tokens, every Haiku write and fix on the hardest task stopped at the limit, so its code was cut off. The failure looked like poor quality.
- **Decision.** Raise the allowance to 64,000 and stream every call, so a large allowance cannot hit an HTTP timeout. Report output-limit stops as their own column.
- **What we give up.** The budget reservation per call is larger, so the cap admits fewer calls in parallel.
- **Revisit when.** A model's replies approach 64,000 tokens. The latency table reports the stops.

## D5. Refusal fallback off

- **Context.** Server-side fallback lets the API answer a refused request with a different model.
- **Decision.** Leave it off. A refusal is logged and counts as a failed step.
- **What we give up.** Resilience to refusals. There were none in the published run.
- **Revisit when.** Refusals appear in the logs.

## D6. Cache entries isolated by policy and by run

- **Context.** Caches match on an exact prefix, per model. Without a label, two cached policies on the same model would share an entry. The first full run also showed that a run started within the cache lifetime of an earlier one begins warm: three of four cached policies logged no cache writes.
- **Decision.** Start the system prompt with a label naming the policy and the run. Discard the warm run and rerun from cold. Count cache writes in the report.
- **What we give up.** A label of about 20 tokens on every call, and the cost of the discarded run (US$27.02).
- **Revisit when.** Never. The cold rerun is the only one published.

## D7. Hard budget cap with worst-case reservation

- **Context.** Concurrent calls of unknown output length can overshoot a cap that is checked after the fact.
- **Decision.** Reserve each call's worst-case cost before it is made, settle with the actual cost after, and refuse any call whose reservation could pass the cap.
- **What we give up.** Parallelism near the cap, because reservations are pessimistic.
- **Revisit when.** Runs are large enough for that to matter.

## D8. A pass needs a clean pytest summary

- **Context.** Generated code is untrusted. It could exit with status 0 before any test runs, or skip the tests it would fail.
- **Decision.** A pass needs exit code 0, at least one passed test, and no failures, errors or skips. The hidden tests never skip.
- **What we give up.** Nothing in this workload.
- **Revisit when.** A task legitimately needs skipped tests.
