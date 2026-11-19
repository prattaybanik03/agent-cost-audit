"""Turns one run's raw logs into results/summary.csv, results/report.md and results/chart.png.

Every number in the outputs is computed here from results/raw/<run_id>/. Nothing is typed in by
hand. `inject_readme` copies the report's tables into the README between two marker comments.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import FormatStrFormatter

README_START = "<!-- results:start -->"
README_END = "<!-- results:end -->"

# Chart colours: validated as a pair for colour-vision deficiency and contrast on the surface.
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
GRID = "#e4e3df"
UNCACHED = "#2a78d6"
CACHED = "#eb6834"


@dataclass
class RunData:
    run_dir: Path
    meta: dict
    task_runs: pd.DataFrame
    calls: pd.DataFrame


def load_run(run_dir: str | Path) -> RunData:
    run_dir = Path(run_dir)
    meta = json.loads((run_dir / "run_meta.json").read_text(encoding="utf-8"))
    task_runs = pd.read_json(run_dir / "task_runs.jsonl", lines=True)
    calls = pd.read_json(run_dir / "calls.jsonl", lines=True)
    return RunData(run_dir, meta, task_runs, calls)


def _percentile(values: pd.Series, q: float) -> float:
    return float(values.quantile(q)) if len(values) else math.nan


def summarise(data: RunData) -> pd.DataFrame:
    """One row per task x policy, over the completed repetitions."""
    runs = data.task_runs[data.task_runs["status"] == "complete"].copy()
    difficulty = {task["id"]: task["difficulty"] for task in data.meta["tasks"]}
    calls = data.calls
    rows = []
    for (task_id, policy), group in runs.groupby(["task_id", "policy"], sort=False):
        reps = set(group["rep"])
        these = calls[
            (calls["task_id"] == task_id) & (calls["policy"] == policy) & calls["rep"].isin(reps)
        ]
        prompt_tokens = (
            these["input_tokens"] + these["cache_write_tokens"] + these["cache_read_tokens"]
        ).sum()
        rows.append(
            {
                "task_id": task_id,
                "difficulty": difficulty.get(task_id, ""),
                "policy": policy,
                "runs": len(group),
                "pass_rate": group["passed"].mean(),
                "first_try_rate": (group["passed"] & (group["fix_attempts"] == 0)).mean(),
                "cost_mean_usd": group["cost_usd"].mean(),
                "cost_min_usd": group["cost_usd"].min(),
                "cost_max_usd": group["cost_usd"].max(),
                "cost_sd_usd": group["cost_usd"].std(ddof=1) if len(group) > 1 else 0.0,
                "wall_time_mean_s": group["wall_time_s"].mean(),
                "calls_mean": group["calls"].mean(),
                "fix_attempts_mean": group["fix_attempts"].mean(),
                "escalations_mean": group["escalations"].mean(),
                "call_latency_p50_ms": _percentile(these["latency_ms"], 0.50),
                "call_latency_p95_ms": _percentile(these["latency_ms"], 0.95),
                "output_tokens_mean": these["output_tokens"].sum() / len(group),
                "cache_read_share": (these["cache_read_tokens"].sum() / prompt_tokens)
                if prompt_tokens
                else 0.0,
                "max_tokens_stops": int((these["stop_reason"] == "max_tokens").sum()),
                "refusals": int((these["stop_reason"] == "refusal").sum()),
            }
        )
    return pd.DataFrame(rows)


def policy_totals(data: RunData, summary: pd.DataFrame) -> pd.DataFrame:
    """One row per policy. Workload cost is the sum of mean cost per task over all tasks."""
    runs = data.task_runs[data.task_runs["status"] == "complete"]
    n_tasks = len(data.meta["tasks"])
    rows = []
    for policy in [p["name"] for p in data.meta["policies"]]:
        mine = summary[summary["policy"] == policy]
        if mine.empty:
            continue
        policy_runs = runs[runs["policy"] == policy]
        per_rep = policy_runs.groupby("rep").agg(
            cost=("cost_usd", "sum"), tasks=("task_id", "count")
        )
        full_reps = per_rep[per_rep["tasks"] == n_tasks]["cost"]
        passes = int(policy_runs["passed"].sum())
        workload = mine["cost_mean_usd"].sum()
        policy_calls = data.calls[data.calls["policy"] == policy]
        first_try = int((policy_runs["passed"] & (policy_runs["fix_attempts"] == 0)).sum())
        first_low, first_high = wilson_interval(first_try, len(policy_runs))
        rows.append(
            {
                "policy": policy,
                "tasks_covered": len(mine),
                "runs": len(policy_runs),
                "pass_rate": policy_runs["passed"].mean(),
                "first_try_rate": first_try / len(policy_runs) if len(policy_runs) else math.nan,
                "first_try_low": first_low,
                "first_try_high": first_high,
                "fix_attempts": int(policy_runs["fix_attempts"].sum()),
                "workload_cost_usd": workload,
                "workload_cost_min_usd": full_reps.min() if len(full_reps) else math.nan,
                "workload_cost_max_usd": full_reps.max() if len(full_reps) else math.nan,
                "cost_per_pass_usd": policy_runs["cost_usd"].sum() / passes if passes else math.nan,
                "call_latency_p50_ms": _percentile(policy_calls["latency_ms"], 0.50),
                "call_latency_p95_ms": _percentile(policy_calls["latency_ms"], 0.95),
                "task_wall_time_mean_s": policy_runs["wall_time_s"].mean(),
                "escalations": int(policy_runs["escalations"].sum()),
                "max_tokens_stops": int((policy_calls["stop_reason"] == "max_tokens").sum()),
            }
        )
    totals = pd.DataFrame(rows)
    baseline = data.meta["baseline"]
    base_cost = totals.loc[totals["policy"] == baseline, "workload_cost_usd"]
    totals["cost_change_vs_baseline"] = (
        totals["workload_cost_usd"] / float(base_cost.iloc[0]) - 1 if len(base_cost) else math.nan
    )
    return totals


def losses(data: RunData, summary: pd.DataFrame) -> pd.DataFrame:
    """Every task where a non-baseline policy cost more than the baseline or passed less often."""
    baseline = data.meta["baseline"]
    base = summary[summary["policy"] == baseline].set_index("task_id")
    rows = []
    for _, row in summary[summary["policy"] != baseline].iterrows():
        if row["task_id"] not in base.index:
            continue
        ref = base.loc[row["task_id"]]
        costlier = row["cost_mean_usd"] > ref["cost_mean_usd"]
        worse = row["pass_rate"] < ref["pass_rate"]
        if not (costlier or worse):
            continue
        reasons = []
        if row["max_tokens_stops"]:
            reasons.append(f"{row['max_tokens_stops']} replies cut off at the output limit")
        if row["escalations_mean"] > 0:
            reasons.append(
                f"escalated to the strong model in {row['escalations_mean']:.0%} of runs"
            )
        if row["fix_attempts_mean"] > ref["fix_attempts_mean"]:
            mine, theirs = row["fix_attempts_mean"], ref["fix_attempts_mean"]
            reasons.append(f"{mine:.1f} fix attempts per run vs {theirs:.1f}")
        if row["output_tokens_mean"] > ref["output_tokens_mean"] * 1.25:
            reasons.append(
                f"{row['output_tokens_mean']:,.0f} output tokens per run vs "
                f"{ref['output_tokens_mean']:,.0f}"
            )
        if row["refusals"]:
            reasons.append(f"{row['refusals']} refusals")
        rows.append(
            {
                "task_id": row["task_id"],
                "difficulty": row["difficulty"],
                "policy": row["policy"],
                "cost_mean_usd": row["cost_mean_usd"],
                "baseline_cost_usd": ref["cost_mean_usd"],
                "pass_rate": row["pass_rate"],
                "baseline_pass_rate": ref["pass_rate"],
                "lost_on": " and ".join(
                    part for part, hit in (("cost", costlier), ("quality", worse)) if hit
                ),
                "why": "; ".join(reasons) or "failed the hidden tests more often",
            }
        )
    return pd.DataFrame(rows)


def cost_breakdown(data: RunData) -> pd.DataFrame:
    """Per policy: the share of spend by step, and the share that paid for output tokens."""
    calls = data.calls
    output_price = {m: p["output"] for m, p in data.meta["prices"]["models"].items()}
    rows = []
    for policy in [p["name"] for p in data.meta["policies"]]:
        mine = calls[calls["policy"] == policy]
        total = mine["cost_usd"].sum()
        if not total:
            continue
        by_step = mine.groupby("step")["cost_usd"].sum()
        output_cost = (mine["output_tokens"] * mine["model"].map(output_price)).sum() / 1_000_000
        rows.append(
            {
                "policy": policy,
                "plan_share": by_step.get("plan", 0.0) / total,
                "write_share": by_step.get("write", 0.0) / total,
                "fix_share": by_step.get("fix", 0.0) / total,
                "output_share": output_cost / total,
            }
        )
    return pd.DataFrame(rows)


def wilson_interval(successes: int, trials: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a proportion. Better behaved than the normal approximation
    near 0% and 100% and at small n."""
    if trials == 0:
        return math.nan, math.nan
    p = successes / trials
    denominator = 1 + z * z / trials
    centre = (p + z * z / (2 * trials)) / denominator
    half = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denominator
    return max(0.0, centre - half), min(1.0, centre + half)


def _rep_totals(data: RunData, policy: str) -> pd.Series:
    """Workload cost of each complete repetition of one policy, indexed by repetition."""
    runs = data.task_runs[
        (data.task_runs["status"] == "complete") & (data.task_runs["policy"] == policy)
    ]
    per_rep = runs.groupby("rep").agg(cost=("cost_usd", "sum"), tasks=("task_id", "count"))
    return per_rep[per_rep["tasks"] == len(data.meta["tasks"])]["cost"]


def caching_effect(data: RunData, totals: pd.DataFrame, summary: pd.DataFrame) -> pd.DataFrame:
    """Each policy against its cached twin. The rep range pairs repetition k of one with
    repetition k of the other; the repetitions are independent, so it shows spread, not a
    paired effect."""
    rows = []
    by_policy = totals.set_index("policy")
    calls = data.calls
    for name in by_policy.index:
        cached = f"{name}_cached"
        if cached not in by_policy.index:
            continue
        plain_cost = by_policy.loc[name, "workload_cost_usd"]
        cached_cost = by_policy.loc[cached, "workload_cost_usd"]
        mine = summary[summary["policy"] == cached]
        plain_reps, cached_reps = _rep_totals(data, name), _rep_totals(data, cached)
        shared = plain_reps.index.intersection(cached_reps.index)
        ratios = cached_reps[shared] / plain_reps[shared] - 1
        cached_calls = calls[calls["policy"] == cached]
        rows.append(
            {
                "pair": name,
                "uncached_usd": plain_cost,
                "cached_usd": cached_cost,
                "change": cached_cost / plain_cost - 1,
                "change_min": ratios.min() if len(ratios) else math.nan,
                "change_max": ratios.max() if len(ratios) else math.nan,
                "cache_read_share": mine["cache_read_share"].mean(),
                "cache_write_calls": int((cached_calls["cache_write_tokens"] > 0).sum()),
                "cache_write_tokens": int(cached_calls["cache_write_tokens"].sum()),
                "uncached_pass_rate": by_policy.loc[name, "pass_rate"],
                "cached_pass_rate": by_policy.loc[cached, "pass_rate"],
            }
        )
    return pd.DataFrame(rows)


# ---------- formatting ----------


def _usd(value: float) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "n/a"
    return f"${value:.4f}" if abs(value) < 0.1 else f"${value:.2f}"


def _pct(value: float, signed: bool = False) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "n/a"
    return f"{value:+.0%}" if signed else f"{value:.0%}"


def _table(headers: list[str], rows: list[list[str]], align: str) -> str:
    marks = {"l": "---", "r": "---:"}
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(marks[a] for a in align) + " |"]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(lines)


def render_tables(data: RunData, summary, totals, lost, caching, breakdown) -> str:
    meta = data.meta
    baseline = meta["baseline"]
    parts = []

    parts.append("### Headline: cost and quality by policy\n")
    parts.append(
        f"Workload cost is the mean cost of each task, summed over all {len(meta['tasks'])} "
        f"tasks. The range is the cheapest and dearest full repetition. Change is against "
        f"`{baseline}`. Pass rate is over every task run. First-try rate is the share of task "
        "runs that passed with no fix attempt, with its 95% Wilson interval: two policies whose "
        "intervals overlap are not shown to differ by this run.\n"
    )
    rows = []
    for _, r in totals.sort_values("workload_cost_usd", ascending=False).iterrows():
        rows.append(
            [
                f"`{r['policy']}`",
                _usd(r["workload_cost_usd"]),
                f"{_usd(r['workload_cost_min_usd'])} to {_usd(r['workload_cost_max_usd'])}",
                "baseline" if r["policy"] == baseline else _pct(r["cost_change_vs_baseline"], True),
                _pct(r["pass_rate"]),
                f"{_pct(r['first_try_rate'])} ({_pct(r['first_try_low'])} to "
                f"{_pct(r['first_try_high'])})",
                str(r["fix_attempts"]),
                _usd(r["cost_per_pass_usd"]),
            ]
        )
    parts.append(
        _table(
            ["Policy", "Workload cost", "Range over reps", "Cost vs baseline", "Pass rate",
             "First-try rate", "Fix attempts", "Cost per passed task"],
            rows,
            "lrrrrrrr",
        )
    )  # fmt: skip

    parts.append("\n\n### Caching on its own\n")
    parts.append(
        "Each pair runs the same models on the same steps. The only difference is "
        "`cache_control` on the shared system prompt. Rep range compares repetition k of each; "
        "repetitions are independent, so it shows spread, not a paired effect. Cache writes "
        "counts the calls that paid the write premium. Cache-read share is the fraction of "
        "prompt tokens served from the cache.\n"
    )
    rows = [
        [
            f"`{r['pair']}`",
            _usd(r["uncached_usd"]),
            _usd(r["cached_usd"]),
            _pct(r["change"], True),
            f"{_pct(r['change_min'], True)} to {_pct(r['change_max'], True)}",
            f"{r['cache_write_calls']} ({r['cache_write_tokens']:,} tokens)",
            _pct(r["cache_read_share"]),
            f"{_pct(r['uncached_pass_rate'])} → {_pct(r['cached_pass_rate'])}",
        ]
        for _, r in caching.iterrows()
    ]
    parts.append(
        _table(
            ["Models", "Uncached", "Cached", "Change", "Rep range", "Cache writes",
             "Cache-read share", "Pass rate"],
            rows,
            "lrrrrrrr",
        )
    )  # fmt: skip

    parts.append("\n\n### Where the money goes\n")
    parts.append(
        "Share of each policy's spend by step, and the share that paid for output tokens "
        "(thinking included). Prompt caching can only reduce the rest.\n"
    )
    rows = [
        [
            f"`{r['policy']}`",
            _pct(r["plan_share"]),
            _pct(r["write_share"]),
            _pct(r["fix_share"]),
            _pct(r["output_share"]),
        ]
        for _, r in breakdown.iterrows()
    ]
    parts.append(_table(["Policy", "Plan", "Write", "Fix", "Output tokens"], rows, "lrrrr"))

    parts.append("\n\n### Where the cheaper route lost\n")
    if lost.empty:
        parts.append(f"No policy cost more than `{baseline}` or passed less often on any task.")
    else:
        parts.append(
            f"Every task where a policy cost more than `{baseline}` on average, or passed less "
            "often. The reasons are read from the call logs.\n"
        )
        order = {"easy": 0, "medium": 1, "hard": 2}
        lost = lost.assign(_d=lost["difficulty"].map(order)).sort_values(
            ["_d", "task_id", "policy"]
        )
        rows = [
            [
                f"`{r['task_id']}`",
                f"`{r['policy']}`",
                r["lost_on"],
                f"${r['cost_mean_usd']:.4f} vs ${r['baseline_cost_usd']:.4f} "
                f"({r['cost_mean_usd'] / r['baseline_cost_usd'] - 1:+.1%})",
                f"{_pct(r['pass_rate'])} vs {_pct(r['baseline_pass_rate'])}",
                r["why"],
            ]
            for _, r in lost.iterrows()
        ]
        parts.append(
            _table(["Task", "Policy", "Lost on", "Cost", "Pass rate", "Why"], rows, "lllrrl")
        )

    parts.append("\n\n### Latency\n")
    parts.append(
        "Call latency is the time from sending a request to receiving the full streamed reply. "
        "Task time includes every call and every test run for that task.\n"
    )
    rows = [
        [
            f"`{r['policy']}`",
            f"{r['call_latency_p50_ms'] / 1000:.1f} s",
            f"{r['call_latency_p95_ms'] / 1000:.1f} s",
            f"{r['task_wall_time_mean_s']:.0f} s",
            str(r["escalations"]),
            str(r["max_tokens_stops"]),
        ]
        for _, r in totals.iterrows()
    ]
    parts.append(
        _table(
            [
                "Policy",
                "Call p50",
                "Call p95",
                "Mean task time",
                "Escalations",
                "Output-limit stops",
            ],
            rows,
            "lrrrrr",
        )
    )

    parts.append("\n\n### Pass rate by task\n")
    policies = [p["name"] for p in meta["policies"]]
    grid = summary.pivot(index="task_id", columns="policy", values="pass_rate")
    rows = [
        [f"`{task['id']}` ({task['difficulty']})"]
        + [_pct(grid.loc[task["id"], p]) if task["id"] in grid.index and p in grid else "n/a"
           for p in policies]
        for task in meta["tasks"]
    ]  # fmt: skip
    parts.append(_table(["Task"] + [f"`{p}`" for p in policies], rows, "l" + "r" * len(policies)))
    return "\n".join(parts) + "\n"


def render_readme_tables(data: RunData, totals, caching, breakdown) -> str:
    """The short version of the results for the README. Same numbers as the full report."""
    baseline = data.meta["baseline"]
    order = totals.sort_values("workload_cost_usd", ascending=False)
    parts = [
        "| Policy | Cost per run of all 10 tasks | vs Opus | Passed | First try (95% interval) |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for _, r in order.iterrows():
        change = "baseline" if r["policy"] == baseline else _pct(r["cost_change_vs_baseline"], True)
        parts.append(
            f"| `{r['policy']}` | {_usd(r['workload_cost_usd'])} | {change} | "
            f"{r['pass_rate'] * r['runs']:.0f}/{r['runs']} | "
            f"{_pct(r['first_try_rate'])} ({_pct(r['first_try_low'])} to "
            f"{_pct(r['first_try_high'])}) |"
        )
    parts += [
        "",
        "**What caching added on its own** (same models, same steps, only `cache_control` "
        "differs), and how much of each policy's spend was output tokens, which caching cannot "
        "reduce:",
        "",
        "| Models | Saving from caching | Range over repetitions | Cache writes | "
        "Output share of spend |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    output_share = breakdown.set_index("policy")["output_share"]
    for _, r in caching.iterrows():
        parts.append(
            f"| `{r['pair']}` | {_pct(r['change'], True)} | "
            f"{_pct(r['change_min'], True)} to {_pct(r['change_max'], True)} | "
            f"{r['cache_write_calls']} | {_pct(output_share.get(r['pair'], math.nan))} |"
        )
    return "\n".join(parts) + "\n"


def render_report(data: RunData, tables: str) -> str:
    meta = data.meta
    prices = meta["prices"]
    dirty = meta.get("git_dirty")
    if dirty is None:
        code_state = (
            f"Code at commit `{meta.get('git_commit')}`; whether the working tree had "
            "uncommitted changes was not recorded for this run, so the commit may not fully "
            "describe the code that ran."
        )
    elif dirty:
        code_state = (
            f"Code at commit `{meta.get('git_commit')}` **plus uncommitted changes**, so the "
            "commit does not fully describe the code that ran."
        )
    else:
        code_state = f"Code at commit `{meta.get('git_commit')}`, with no uncommitted changes."
    lines = [
        "# Results",
        "",
        f"Run `{meta['run_id']}`, started {meta['started_at']} and finished "
        f"{meta.get('finished_at', 'unknown')}. {code_state}",
        "",
        f"- Provider: {meta['provider']}. Token counts {meta['token_counts']}.",
        f"- {len(meta['tasks'])} tasks x {len(meta['policies'])} policies x "
        f"{meta['repetitions']} repetition{'s' if meta['repetitions'] != 1 else ''}. "
        f"{meta.get('completed_task_runs')} of "
        f"{meta.get('planned_task_runs')} task runs completed.",
        f"- Total API spend for this run: ${meta.get('spent_usd', 0):.2f} "
        f"(cap ${meta['budget_cap_usd']:.2f}).",
        f"- Effort `{meta['effort']}` on every call. Output allowance {meta['max_tokens']:,} "
        f"tokens per call. Up to {meta['max_fix_attempts']} fix attempts per task.",
        f"- Sandbox: {meta['sandbox']} (network "
        f"{'blocked' if meta['sandbox_isolates_network'] else 'NOT blocked'}).",
        f"- Prices from {prices['source_url']}, checked {prices['date_checked']}.",
    ]
    if meta.get("stopped_reason"):
        lines.append(f"- **The run stopped early:** {meta['stopped_reason']}")
    lines += ["", tables]
    return "\n".join(lines)


def render_chart(data: RunData, totals: pd.DataFrame, path: Path) -> None:
    """Mean cost per task for each model setup, uncached and cached side by side."""
    by_policy = totals.set_index("policy")
    n_tasks = len(data.meta["tasks"])
    groups = [name for name in by_policy.index if not name.endswith("_cached")]

    fig, ax = plt.subplots(figsize=(9, 5.2), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    width = 0.3
    top = 0.0
    series = (
        (-0.19, "", UNCACHED, "No caching"),
        (0.19, "_cached", CACHED, "System prompt cached"),
    )
    for offset, suffix, colour, label in series:
        xs, heights, lows, highs, rates = [], [], [], [], []
        for index, group in enumerate(groups):
            name = group + suffix
            if name not in by_policy.index:
                continue
            row = by_policy.loc[name]
            xs.append(index + offset)
            heights.append(row["workload_cost_usd"] / n_tasks)
            lows.append(row["workload_cost_min_usd"] / n_tasks)
            highs.append(row["workload_cost_max_usd"] / n_tasks)
            rates.append(row["pass_rate"])
        ax.bar(xs, heights, width=width, color=colour, label=label, zorder=2,
               edgecolor=SURFACE, linewidth=2)  # fmt: skip
        spread = [
            [h - lo if not math.isnan(lo) else 0 for h, lo in zip(heights, lows, strict=True)],
            [hi - h if not math.isnan(hi) else 0 for h, hi in zip(heights, highs, strict=True)],
        ]
        ax.errorbar(xs, heights, yerr=spread, fmt="none", ecolor=INK_SECONDARY, elinewidth=1,
                    capsize=3, zorder=3)  # fmt: skip
        for x, h, hi, rate in zip(xs, heights, highs, rates, strict=True):
            label_y = hi if not math.isnan(hi) else h
            top = max(top, label_y)
            ax.annotate(f"${h:.3f}\n{rate:.0%} pass", (x, label_y), xytext=(0, 4),
                        textcoords="offset points", ha="center", va="bottom", fontsize=8,
                        color=INK)  # fmt: skip

    ax.set_xticks(range(len(groups)))
    ax.set_xticklabels([g.capitalize() if g != "routed" else "Routed\n(Opus plans, Haiku writes)"
                        for g in groups], color=INK)  # fmt: skip
    ax.set_ylabel("Mean API cost per task (US$)", color=INK)
    ax.set_ylim(0, top * 1.25 if top else 1)
    ax.yaxis.set_major_formatter(FormatStrFormatter("$%.3f"))
    ax.grid(axis="y", color=GRID, linewidth=1, zorder=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK_SECONDARY, length=0)
    ax.set_title(
        f"Cost per task by policy, with pass rate ({n_tasks} coding tasks, "
        f"{data.meta['repetitions']} repetition{'s' if data.meta['repetitions'] != 1 else ''})",
        color=INK, fontsize=11, loc="left",
    )  # fmt: skip
    ax.legend(frameon=False, loc="upper right", labelcolor=INK)
    fig.text(0.01, 0.01, "Whiskers: cheapest and dearest repetition.", fontsize=7,
             color=INK_SECONDARY)  # fmt: skip
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


def write_report(run_dir: str | Path, out_dir: str | Path = "results") -> dict[str, Path]:
    data = load_run(run_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = summarise(data)
    totals = policy_totals(data, summary)
    lost = losses(data, summary)
    caching = caching_effect(data, totals, summary)
    breakdown = cost_breakdown(data)
    tables = render_tables(data, summary, totals, lost, caching, breakdown)

    paths = {
        "summary": out_dir / "summary.csv",
        "report": out_dir / "report.md",
        "chart": out_dir / "chart.png",
        "tables": out_dir / "tables.md",
        "readme_tables": out_dir / "readme-tables.md",
    }
    summary.round(6).to_csv(paths["summary"], index=False)
    paths["report"].write_text(render_report(data, tables), encoding="utf-8")
    paths["tables"].write_text(tables, encoding="utf-8")
    paths["readme_tables"].write_text(
        render_readme_tables(data, totals, caching, breakdown), encoding="utf-8"
    )
    render_chart(data, totals, paths["chart"])
    return paths


def inject_readme(readme: str | Path, tables: str) -> None:
    """Replace the text between the results markers in the README with `tables`."""
    path = Path(readme)
    text = path.read_text(encoding="utf-8")
    start, end = text.find(README_START), text.find(README_END)
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"{path} lacks the {README_START} / {README_END} markers.")
    head = text[: start + len(README_START)]
    path.write_text(head + "\n\n" + tables.strip() + "\n\n" + text[end:], encoding="utf-8")
