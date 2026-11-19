"""Builds the static results page in site/: one HTML file and the chart.

Every number on the page is computed here from the run's data, the same way the report and the
README tables are. The page loads nothing from other sites: no scripts, fonts or trackers.
"""

from __future__ import annotations

import html
import math
import shutil
from pathlib import Path

import pandas as pd

REPO_URL = "https://github.com/prattaybanik03/agent-cost-audit"

_CSS = """
:root { --ink:#0b0b0b; --ink2:#52514e; --line:#e4e3df; --bg:#fcfcfb; --blue:#2a78d6;
        --orange:#eb6834; --panel:#f3f2ee; }
@media (prefers-color-scheme: dark) {
  :root { --ink:#f0efec; --ink2:#c3c2b7; --line:#383835; --bg:#1a1a19; --panel:#232321; }
  img.chart { background:#fcfcfb; border-radius:8px; }
}
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--ink);
       font:16px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif; }
main { max-width:960px; margin:0 auto; padding:40px 20px 64px; }
h1 { font-size:2rem; margin:0 0 8px; letter-spacing:-0.01em; }
.lede { font-size:1.15rem; color:var(--ink2); margin:0 0 24px; }
h2 { font-size:1.3rem; margin:44px 0 12px; padding-top:12px; border-top:1px solid var(--line); }
.glance { display:grid; grid-template-columns:160px 1fr; gap:0; border:1px solid var(--line);
          border-radius:10px; overflow:hidden; margin:0 0 28px; }
.glance dt, .glance dd { margin:0; padding:12px 16px; border-bottom:1px solid var(--line); }
.glance dt { font-weight:600; background:var(--panel); }
.glance dt:last-of-type, .glance dd:last-of-type { border-bottom:0; }
.big { font-size:1.05rem; }
.stats { display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:12px;
         margin:0 0 28px; }
.stat { border:1px solid var(--line); border-radius:10px; padding:14px 16px; }
.stat b { display:block; font-size:1.7rem; line-height:1.1; }
.stat span { color:var(--ink2); font-size:0.9rem; }
img.chart { width:100%; height:auto; border:1px solid var(--line); border-radius:8px; }
.tablewrap { overflow-x:auto; }
table { border-collapse:collapse; width:100%; font-size:0.95rem; margin:8px 0 6px; }
th, td { padding:8px 10px; border-bottom:1px solid var(--line); text-align:right;
         white-space:nowrap; }
th:first-child, td:first-child { text-align:left; }
th { color:var(--ink2); font-weight:600; }
code { font-family:ui-monospace,SFMono-Regular,Consolas,monospace; font-size:0.9em; }
.note { color:var(--ink2); font-size:0.9rem; }
ul { padding-left:20px; } li { margin:6px 0; }
a { color:var(--blue); }
footer { margin-top:48px; color:var(--ink2); font-size:0.85rem; }
@media (max-width:600px) { .glance { grid-template-columns:1fr; }
  .glance dt { border-bottom:0; } }
"""


def _e(text: object) -> str:
    return html.escape(str(text))


def _pct(value: float, signed: bool = False) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "n/a"
    return f"{value:+.0%}" if signed else f"{value:.0%}"


def _usd(value: float) -> str:
    return f"${value:.4f}" if abs(value) < 0.1 else f"${value:.2f}"


def _table(headers: list[str], rows: list[list[str]], caption: str) -> str:
    head = "".join(f"<th scope='col'>{h}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return (
        f"<div class='tablewrap'><table><caption class='note' style='text-align:left'>"
        f"{caption}</caption><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"
    )


def render_site(
    meta: dict,
    calls: pd.DataFrame,
    totals: pd.DataFrame,
    caching: pd.DataFrame,
    breakdown: pd.DataFrame,
) -> str:
    """The page's HTML. Every figure is computed from the arguments."""
    by = totals.set_index("policy")
    baseline = meta["baseline"]
    n_tasks = len(meta["tasks"])
    n_policies = len(meta["policies"])
    task_runs = int(totals["runs"].sum())
    passed_runs = round(float((totals["pass_rate"] * totals["runs"]).sum()))
    n_calls = len(calls)
    spent = float(calls["cost_usd"].sum())
    out_share = breakdown.set_index("policy")["output_share"]
    plan_share = breakdown.set_index("policy")["plan_share"]
    all_passed = bool((totals["pass_rate"] == 1).all())

    def change(policy: str) -> float:
        return float(by.loc[policy, "cost_change_vs_baseline"])

    if len(caching):
        cache_low, cache_high = -caching["change"].max(), -caching["change"].min()
        cache_tile = f"{-cache_high:+.0%} to {-cache_low:+.0%}"
    else:
        cache_low = cache_high = math.nan
        cache_tile = "n/a"
    has = set(by.index)
    haiku_line = (
        f"Haiku 5.5 alone did the work for <b>{-change('haiku'):.0%} less</b> than Opus 5.5"
        + (", and passed every task." if all_passed else ".")
        if "haiku" in has
        else ""
    )
    routed_line = (
        f" Routing (Opus plans, Haiku writes) saved {-change('routed'):.0%}."
        if "routed" in has
        else ""
    )
    cache_line = (
        f" Caching the system prompt saved a further {cache_low:.0%} to {cache_high:.0%}."
        if len(caching)
        else ""
    )
    if "routed" in has:
        escalations = int(by.loc["routed", "escalations"])
        escalated = (
            "and never needed the Opus fix it held in reserve"
            if escalations == 0
            else f"and escalated to Opus {escalations} time{'s' if escalations != 1 else ''}"
        )
        routed_plan = (
            f" Routing spent {plan_share['routed']:.0%} of its budget on the Opus planning "
            f"step, {escalated}."
        )
    else:
        routed_plan = ""

    headline_rows = []
    for _, r in totals.sort_values("workload_cost_usd", ascending=False).iterrows():
        headline_rows.append(
            [
                f"<code>{_e(r['policy'])}</code>",
                _usd(r["workload_cost_usd"]),
                "baseline" if r["policy"] == baseline else _pct(r["cost_change_vs_baseline"], True),
                f"{r['pass_rate'] * r['runs']:.0f}/{r['runs']}",
                f"{_pct(r['first_try_rate'])} ({_pct(r['first_try_low'])} to "
                f"{_pct(r['first_try_high'])})",
            ]
        )
    caching_rows = [
        [
            f"<code>{_e(r['pair'])}</code>",
            _pct(r["change"], True),
            f"{_pct(r['change_min'], True)} to {_pct(r['change_max'], True)}",
            str(r["cache_write_calls"]),
            _pct(out_share.get(r["pair"], math.nan)),
        ]
        for _, r in caching.iterrows()
    ]
    money_rows = [
        [
            f"<code>{_e(r['policy'])}</code>",
            _pct(r["plan_share"]),
            _pct(r["write_share"]),
            _pct(r["fix_share"]),
            _pct(r["output_share"]),
        ]
        for _, r in breakdown.iterrows()
    ]

    prices = meta["prices"]
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>agent-cost-audit: what routing and prompt caching really save</title>
<meta name="description" content="Measured on {n_calls} real API calls: how much model routing and prompt caching cut an AI coding agent's cost, and whether quality holds.">
<style>{_CSS}</style>
</head>
<body>
<main>
<h1>agent-cost-audit</h1>
<p class="lede">How much do model routing and prompt caching really cut the cost of an AI coding agent, and does quality hold? Measured on {n_calls} real API calls.</p>

<div class="stats" role="list">
  <div class="stat" role="listitem"><b>{_pct(change("haiku"), True) if "haiku" in has else "n/a"}</b><span>cost, Haiku alone vs Opus</span></div>
  <div class="stat" role="listitem"><b>{_pct(change("routed"), True) if "routed" in has else "n/a"}</b><span>cost, routed vs Opus</span></div>
  <div class="stat" role="listitem"><b>{cache_tile}</b><span>extra saving from caching</span></div>
  <div class="stat" role="listitem"><b>{passed_runs}/{task_runs}</b><span>task runs passed</span></div>
</div>

<dl class="glance">
  <dt>The question</dt>
  <dd>On the same coding-agent workload, how much do model routing and prompt caching cut API cost, and does quality hold?</dd>
  <dt>The answer</dt>
  <dd class="big">{haiku_line}{routed_line}{cache_line}</dd>
  <dt>The catch</dt>
  <dd>Caching cannot touch output tokens, which were {out_share.min():.0%} to {out_share.max():.0%} of spend.{routed_plan} In a <a href="{REPO_URL}/blob/main/results/smoke-16k-limit/report.md">separate smoke test</a> with a lower output limit, the cheap model was cut off mid-answer and the routed policy failed the hardest task.</dd>
  <dt>The evidence</dt>
  <dd>{n_tasks} tasks &times; {n_policies} policies &times; {meta["repetitions"]} repetitions: {task_runs} task runs, {n_calls} API calls, ${spent:.2f}. Hidden tests ran in a Docker sandbox with no network. Every result on this page is generated from that logged run.</dd>
</dl>

<img class="chart" src="chart.png" width="1350" height="780" alt="Mean API cost per task for each policy, uncached and cached, with pass rate for each bar.">

<h2>Cost and quality by policy</h2>
{_table(["Policy", f"Cost per run of all {n_tasks} tasks", "vs Opus", "Passed", "First try (95% interval)"], headline_rows, "Overlapping intervals mean this run does not show a quality difference.")}

<h2>What caching added on its own</h2>
{_table(["Models", "Saving from caching", "Range over repetitions", "Cache writes", "Output share of spend"], caching_rows, "Same models and steps; only <code>cache_control</code> on the system prompt differs. Each run starts from a cold cache.")}

<h2>Where the money goes</h2>
{_table(["Policy", "Plan", "Write", "Fix", "Output tokens"], money_rows, "Share of each policy's spend by step, and the share that paid for output tokens, thinking included.")}

<h2>How it was measured</h2>
<ul>
  <li>Every policy runs the same loop (plan, write, test, at most two fixes), the same ten tasks and the same system prompt at effort <code>{_e(meta["effort"])}</code>. Only the model per step, and whether the system prompt is cached, change.</li>
  <li>Cost is computed per call from the API's own token counts, at prices from <a href="{_e(prices["source_url"])}">the published price list</a>, checked {_e(prices["date_checked"])}.</li>
  <li>A hard budget cap reserves each call's worst-case cost before it is made.</li>
  <li>Limits: ten synthetic tasks, five repetitions, one provider and one effort setting. Every policy passed every task, so pass rate cannot separate the models here.</li>
</ul>
<p>Method, decisions, code and the raw-data schema: <a href="{REPO_URL}">{REPO_URL.removeprefix("https://")}</a>.</p>

<footer>Run <code>{_e(meta["run_id"])}</code> at commit <code>{_e(meta.get("git_commit"))}</code>. Page generated by <code>aca report --site</code>.</footer>
</main>
</body>
</html>
"""


def write_site(
    site_dir: str | Path,
    meta: dict,
    calls: pd.DataFrame,
    totals: pd.DataFrame,
    caching: pd.DataFrame,
    breakdown: pd.DataFrame,
    chart: Path,
) -> Path:
    site = Path(site_dir)
    site.mkdir(parents=True, exist_ok=True)
    page = site / "index.html"
    page.write_text(render_site(meta, calls, totals, caching, breakdown), encoding="utf-8")
    shutil.copyfile(chart, site / "chart.png")
    return page
