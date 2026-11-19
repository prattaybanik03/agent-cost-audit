from __future__ import annotations

import pandas as pd
import pytest

import aca.runner as runner_module
from aca.agent import Task, TestResult
from aca.providers.mock import MockProvider, estimate_tokens
from aca.report import (
    README_END,
    README_START,
    caching_effect,
    inject_readme,
    load_run,
    losses,
    policy_totals,
    summarise,
    wilson_interval,
    write_report,
)
from aca.runner import run_benchmark

TASKS = [
    Task(task_id="t_easy", prompt="Easy.", test_code="", difficulty="easy"),
    Task(task_id="t_hard", prompt="Hard.", test_code="", difficulty="hard"),
]


class NullSandbox:
    name = "scripted"
    isolates_network = False


def scripted(task: Task, code: str) -> TestResult:
    """Every policy passes the easy task. Only Opus-written code passes the hard one."""
    passed = task.task_id == "t_easy" or "opus" in code
    return TestResult(passed=passed, output="2 passed" if passed else "1 failed, 1 passed")


@pytest.fixture
def run_dir(tmp_path, config, prices, monkeypatch):
    monkeypatch.setattr(runner_module, "as_test_runner", lambda sandbox: scripted)
    provider = MockProvider(lambda model, system, messages: f"```python\n# {model}\n```")
    names = ["opus", "opus_cached", "haiku", "routed"]
    run_benchmark(
        provider=provider,
        config=config,
        prices=prices,
        tasks=TASKS,
        policies=[config.policy(name) for name in names],
        repetitions=2,
        sandbox=NullSandbox(),
        estimate_tokens=estimate_tokens,
        out_root=tmp_path / "raw",
        workers=2,
        run_id="r",
        echo=lambda line: None,
    )
    return tmp_path / "raw" / "r"


def test_summary_has_one_row_per_task_and_policy(run_dir) -> None:
    summary = summarise(load_run(run_dir))
    assert len(summary) == 2 * 4
    assert set(summary["runs"]) == {2}
    hard = summary.set_index(["task_id", "policy"])
    assert hard.loc[("t_hard", "opus"), "pass_rate"] == 1.0
    assert hard.loc[("t_hard", "haiku"), "pass_rate"] == 0.0
    # Routed escalates to Opus on the second fix, which passes.
    assert hard.loc[("t_hard", "routed"), "pass_rate"] == 1.0
    assert hard.loc[("t_hard", "routed"), "escalations_mean"] == 1.0


def test_totals_match_the_call_log(run_dir) -> None:
    data = load_run(run_dir)
    totals = policy_totals(data, summarise(data)).set_index("policy")
    for policy in totals.index:
        logged = data.calls[data.calls["policy"] == policy]["cost_usd"].sum()
        # Workload cost is the per-task mean summed over tasks, i.e. logged spend / repetitions.
        assert totals.loc[policy, "workload_cost_usd"] == pytest.approx(logged / 2)
    assert totals.loc["opus", "cost_change_vs_baseline"] == pytest.approx(0.0)
    assert totals.loc["haiku", "cost_change_vs_baseline"] < 0


def test_losses_name_the_task_and_the_reason(run_dir) -> None:
    data = load_run(run_dir)
    lost = losses(data, summarise(data))
    haiku_hard = lost[(lost["policy"] == "haiku") & (lost["task_id"] == "t_hard")]
    assert len(haiku_hard) == 1
    assert "quality" in haiku_hard.iloc[0]["lost_on"]
    routed_hard = lost[(lost["policy"] == "routed") & (lost["task_id"] == "t_hard")]
    if len(routed_hard):  # routed lost on cost, if at all, never on quality here
        assert routed_hard.iloc[0]["lost_on"] == "cost"
        assert "escalated" in routed_hard.iloc[0]["why"]
    # Every policy passes the easy task, so it can only ever appear as a cost loss.
    easy = lost[lost["task_id"] == "t_easy"]
    assert (easy["lost_on"] == "cost").all()


def test_write_report_produces_every_file(run_dir, tmp_path) -> None:
    paths = write_report(run_dir, tmp_path / "results")
    for key in ("summary", "report", "chart", "tables"):
        assert paths[key].exists() and paths[key].stat().st_size > 0
    assert paths["chart"].read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    csv = pd.read_csv(paths["summary"])
    assert len(csv) == 8
    report = paths["report"].read_text(encoding="utf-8")
    assert "Token counts estimated (mock)" in report
    assert "Where the cheaper route lost" in report
    assert "https://" in report  # price source


def test_inject_readme_replaces_only_the_marked_section(run_dir, tmp_path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text(f"# Title\n\n{README_START}\nold\n{README_END}\n\nFooter\n", encoding="utf-8")
    inject_readme(readme, "| new | table |")
    text = readme.read_text(encoding="utf-8")
    assert "old" not in text and "| new | table |" in text
    assert text.startswith("# Title") and text.rstrip().endswith("Footer")
    inject_readme(readme, "| newer |")  # idempotent: can be run again
    assert "| new | table |" not in readme.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("successes", "trials", "low", "high"),
    [(47, 50, 0.838, 0.979), (42, 50, 0.715, 0.917), (50, 50, 0.929, 1.0), (0, 10, 0.0, 0.278)],
)
def test_wilson_interval_matches_published_values(successes, trials, low, high) -> None:
    got_low, got_high = wilson_interval(successes, trials)
    assert got_low == pytest.approx(low, abs=0.001)
    assert got_high == pytest.approx(high, abs=0.001)


def test_caching_table_counts_cache_writes(run_dir) -> None:
    data = load_run(run_dir)
    summary = summarise(data)
    caching = caching_effect(data, policy_totals(data, summary), summary).set_index("pair")
    # The mock writes the cache on a model's first call in a policy, then reads it.
    assert caching.loc["opus", "cache_write_calls"] >= 1
    assert caching.loc["opus", "change_min"] <= caching.loc["opus", "change_max"]


def test_report_states_whether_the_tree_was_dirty(run_dir, tmp_path) -> None:
    report = write_report(run_dir, tmp_path / "out")["report"].read_text(encoding="utf-8")
    assert "uncommitted changes" in report


def test_inject_readme_requires_markers(tmp_path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("no markers here", encoding="utf-8")
    with pytest.raises(ValueError):
        inject_readme(readme, "x")
