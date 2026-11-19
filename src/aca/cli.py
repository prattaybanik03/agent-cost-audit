"""Command line entry point. `aca run` and `aca report` arrive with the workload and providers."""

from __future__ import annotations

import time
from pathlib import Path

import typer
from dotenv import load_dotenv

from aca.agent import TokenEstimator
from aca.policies import load_run_config
from aca.pricing import load_prices
from aca.providers.anthropic import AnthropicProvider, conservative_token_estimate
from aca.providers.base import Provider
from aca.providers.mock import MockProvider, estimate_tokens
from aca.report import inject_readme, write_report
from aca.runner import run_benchmark
from aca.sandbox import DEFAULT_IMAGE, build_image, make_sandbox
from aca.tasks import TASKS_ROOT, load_tasks, reference_code

app = typer.Typer(add_completion=False, no_args_is_help=True, help="Agent cost audit.")

PRICES_PATH = Path("config/prices.yaml")
RUN_PATH = Path("config/run.yaml")
RAW_PATH = Path("results/raw")


@app.command()
def prices(path: Path = PRICES_PATH) -> None:
    """Show the price table and where it came from."""
    table = load_prices(path)
    typer.echo(f"Source: {table.source_url}")
    typer.echo(f"Checked: {table.date_checked}   Currency: {table.currency} per million tokens")
    header = f"{'model':<22}{'input':>8}{'output':>8}{'write 5m':>10}{'write 1h':>10}{'read':>8}"
    typer.echo(header)
    for model, price in table.models.items():
        typer.echo(
            f"{model:<22}{price.input:>8.3f}{price.output:>8.2f}"
            f"{price.cache_write_5m:>10.3f}{price.cache_write_1h:>10.2f}{price.cache_read:>8.2f}"
        )


@app.command()
def policies(run: Path = RUN_PATH, prices_path: Path = PRICES_PATH) -> None:
    """Show the policies in the run config and check every model has a price."""
    config = load_run_config(run)
    config.check_priced(load_prices(prices_path))
    typer.echo(
        f"Budget cap: ${config.budget_cap_usd:.2f}   Repetitions: {config.repetitions}   "
        f"Effort: {config.effort}   Baseline: {config.baseline}"
    )
    typer.echo(f"{'policy':<16}{'plan':<8}{'write':<8}{'fix':<18}{'cache'}")
    for policy in config.policies:
        typer.echo(
            f"{policy.name:<16}{policy.plan:<8}{policy.write:<8}"
            f"{' -> '.join(policy.fix):<18}{'yes' if policy.cache else 'no'}"
        )


def _pick(names: str | None, available: list[str], what: str) -> list[str]:
    if not names:
        return available
    chosen = [name.strip() for name in names.split(",") if name.strip()]
    unknown = [name for name in chosen if name not in available]
    if unknown:
        raise typer.BadParameter(f"Unknown {what}: {', '.join(unknown)}")
    return chosen


@app.command()
def run(
    provider: str = typer.Option("anthropic", help="anthropic or mock"),
    tasks: str = typer.Option(None, help="Comma-separated task IDs. Default: all."),
    policies: str = typer.Option(None, help="Comma-separated policy names. Default: all."),
    reps: int = typer.Option(None, help="Repetitions. Default: from run.yaml."),
    cap: float = typer.Option(None, help="Budget cap in USD. Default: from run.yaml."),
    workers: int = typer.Option(10, help="Task runs in parallel."),
    sandbox: str = typer.Option("auto", help="auto, docker or subprocess"),
    out: Path = RAW_PATH,
    run_config: Path = RUN_PATH,
    prices_path: Path = PRICES_PATH,
) -> None:
    """Run the benchmark and write raw logs to results/raw/<run_id>/."""
    load_dotenv()
    config = load_run_config(run_config)
    table = load_prices(prices_path)
    all_tasks = load_tasks(TASKS_ROOT)
    task_ids = _pick(tasks, [task.task_id for task in all_tasks], "task")
    policy_names = _pick(policies, [policy.name for policy in config.policies], "policy")
    if sandbox not in ("auto", "docker", "subprocess"):
        raise typer.BadParameter("sandbox must be auto, docker or subprocess")
    runner = make_sandbox(sandbox)  # type: ignore[arg-type]

    chosen: Provider
    estimator: TokenEstimator
    if provider == "anthropic":
        chosen = AnthropicProvider(effort=config.effort)
        estimator = conservative_token_estimate
    elif provider == "mock":
        chosen = MockProvider()
        estimator = estimate_tokens
    else:
        raise typer.BadParameter("provider must be anthropic or mock")

    repetitions = reps or config.repetitions
    selected_tasks = [task for task in all_tasks if task.task_id in task_ids]
    selected_policies = [config.policy(name) for name in policy_names]
    total = repetitions * len(selected_tasks) * len(selected_policies)
    typer.echo(
        f"Provider {provider}, sandbox {runner.name} "
        f"(network {'blocked' if runner.isolates_network else 'NOT blocked'}), "
        f"{len(selected_tasks)} tasks x {len(selected_policies)} policies x {repetitions} reps "
        f"= {total} task runs, cap ${cap if cap is not None else config.budget_cap_usd:.2f}"
    )

    summary = run_benchmark(
        provider=chosen,
        config=config,
        prices=table,
        tasks=selected_tasks,
        policies=selected_policies,
        repetitions=repetitions,
        sandbox=runner,
        estimate_tokens=estimator,
        out_root=out,
        workers=workers,
        budget_cap_usd=cap,
        echo=typer.echo,
    )

    typer.echo(f"\nRun {summary.run_id}: {summary.completed}/{summary.planned} task runs complete")
    typer.echo(f"Spent ${summary.spent_usd:.4f}. Raw logs: {summary.out_dir}")
    for name, (passed, ran) in summary.passed_by_policy.items():
        typer.echo(f"  {name:<16}{passed}/{ran} passed")
    if summary.stopped_reason:
        typer.echo(f"Stopped early. {summary.stopped_reason}")
        raise typer.Exit(code=2)


@app.command()
def report(
    run_dir: Path = typer.Argument(..., help="A run folder, e.g. results/raw/<run_id>"),
    out: Path = Path("results"),
    readme: Path = typer.Option(None, help="Also copy the tables into this README."),
) -> None:
    """Write summary.csv, report.md and chart.png from one run's raw logs."""
    paths = write_report(run_dir, out)
    for name, path in paths.items():
        typer.echo(f"{name:<8} {path}")
    if readme is not None:
        inject_readme(readme, paths["readme_tables"].read_text(encoding="utf-8"))
        typer.echo(f"readme   {readme} (results section replaced)")


@app.command("sandbox-build")
def sandbox_build(dockerfile_dir: Path = Path("sandbox")) -> None:
    """Build the Docker image that generated code is tested in."""
    build_image(dockerfile_dir)
    typer.echo(f"Built {DEFAULT_IMAGE}.")


@app.command("tasks-verify")
def tasks_verify(
    sandbox: str = typer.Option("auto", help="auto, docker or subprocess"),
    root: Path = TASKS_ROOT,
) -> None:
    """Check every task: the reference solution must pass and an empty solution must fail."""
    if sandbox not in ("auto", "docker", "subprocess"):
        raise typer.BadParameter("sandbox must be auto, docker or subprocess")
    runner = make_sandbox(sandbox)  # type: ignore[arg-type]
    network = "blocked" if runner.isolates_network else "NOT blocked"
    typer.echo(f"Sandbox: {runner.name} (network {network})")
    typer.echo(f"{'task':<20}{'difficulty':<12}{'reference':<12}{'empty':<10}{'seconds':>8}")

    problems = 0
    for task in load_tasks(root):
        started = time.perf_counter()
        reference = runner.run(task.test_code, reference_code(task.task_id, root))
        elapsed = time.perf_counter() - started
        empty = runner.run(task.test_code, "")
        ok = reference.passed and not empty.passed
        problems += not ok
        typer.echo(
            f"{task.task_id:<20}{task.difficulty:<12}"
            f"{'pass' if reference.passed else 'FAIL':<12}"
            f"{'fails' if not empty.passed else 'PASSES':<10}{elapsed:>8.2f}"
        )
        if not reference.passed:
            typer.echo(reference.output)
    if problems:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
