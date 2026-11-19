from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import aca.runner as runner_module
from aca.agent import Task, TestResult
from aca.providers.mock import MockProvider, estimate_tokens
from aca.report import load_run, policy_totals, summarise, write_report
from aca.runner import run_benchmark

TASKS = [
    Task(task_id="t_easy", prompt="Easy.", test_code="", difficulty="easy"),
    Task(task_id="t_hard", prompt="Hard.", test_code="", difficulty="hard"),
]
SITE_CONFIG = Path(__file__).resolve().parents[1] / "site" / "vercel.json"


class NullSandbox:
    """Satisfies the Sandbox protocol; the tests replace the test runner, so it never runs."""

    name = "scripted"
    isolates_network = False

    def run(self, test_code: str, solution_code: str) -> TestResult:
        raise AssertionError("not used: the test runner is replaced")


@pytest.fixture
def built(tmp_path, config, prices, monkeypatch):
    monkeypatch.setattr(
        runner_module,
        "as_test_runner",
        lambda sandbox: lambda task, code: TestResult(passed=True, output="2 passed"),
    )
    run_benchmark(
        provider=MockProvider(),
        config=config,
        prices=prices,
        tasks=TASKS,
        policies=[config.policy(n) for n in ("opus", "opus_cached", "haiku", "routed")],
        repetitions=2,
        sandbox=NullSandbox(),
        estimate_tokens=estimate_tokens,
        out_root=tmp_path / "raw",
        workers=2,
        run_id="r",
        echo=lambda line: None,
    )
    run_dir = tmp_path / "raw" / "r"
    paths = write_report(run_dir, tmp_path / "results", tmp_path / "site")
    return run_dir, tmp_path / "site", paths


def test_site_has_the_page_and_the_chart(built) -> None:
    _, site, paths = built
    assert paths["site"] == site / "index.html"
    assert (site / "chart.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_site_numbers_come_from_the_run(built) -> None:
    run_dir, site, _ = built
    page = (site / "index.html").read_text(encoding="utf-8")
    data = load_run(run_dir)
    totals = policy_totals(data, summarise(data)).set_index("policy")
    haiku = totals.loc["haiku", "cost_change_vs_baseline"]
    assert f"{haiku:+.0%}" in page
    assert f"{len(data.calls)} real API calls" in page
    assert f"${data.calls['cost_usd'].sum():.2f}" in page


def test_passed_tile_counts_passes_not_runs(tmp_path, config, prices, monkeypatch) -> None:
    """Regression: the tile once printed the run count twice."""
    monkeypatch.setattr(
        runner_module,
        "as_test_runner",
        lambda sandbox: (
            lambda task, code: TestResult(
                passed=task.task_id == "t_easy",
                output="2 passed" if task.task_id == "t_easy" else "",
            )
        ),
    )
    run_benchmark(
        provider=MockProvider(),
        config=config,
        prices=prices,
        tasks=TASKS,
        policies=[config.policy("opus"), config.policy("haiku")],
        repetitions=1,
        sandbox=NullSandbox(),
        estimate_tokens=estimate_tokens,
        out_root=tmp_path / "raw",
        workers=1,
        run_id="half",
        echo=lambda line: None,
    )
    write_report(tmp_path / "raw" / "half", tmp_path / "res", tmp_path / "site")
    page = (tmp_path / "site" / "index.html").read_text(encoding="utf-8")
    assert "<b>2/4</b><span>task runs passed</span>" in page


def test_site_loads_nothing_from_other_sites(built) -> None:
    _, site, _ = built
    page = (site / "index.html").read_text(encoding="utf-8")
    assert "<script" not in page.lower()
    sources = re.findall(r"""(?:src|href)=["']([^"']+)""", page)
    loaded = [s for s in re.findall(r"""src=["']([^"']+)""", page)]
    assert loaded == ["chart.png"]  # the only thing the page loads
    assert all(s.startswith(("https://", "chart.png")) for s in sources)  # links only


def test_site_escapes_text_from_the_run(built, tmp_path) -> None:
    run_dir, _, _ = built
    meta_path = run_dir / "run_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["run_id"] = "<script>alert(1)</script>"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    write_report(run_dir, tmp_path / "results2", tmp_path / "site2")
    page = (tmp_path / "site2" / "index.html").read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page


def test_vercel_config_blocks_scripts_and_framing() -> None:
    config = json.loads(SITE_CONFIG.read_text(encoding="utf-8"))
    headers = {h["key"]: h["value"] for h in config["headers"][0]["headers"]}
    csp = headers["Content-Security-Policy"]
    assert "default-src 'none'" in csp
    assert "script-src" not in csp  # falls back to 'none': no scripts at all
    assert "frame-ancestors 'none'" in csp
