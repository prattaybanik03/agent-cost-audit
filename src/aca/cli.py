"""Command line entry point. `aca run` and `aca report` arrive with the workload and providers."""

from __future__ import annotations

import time
from pathlib import Path

import typer

from aca.policies import load_run_config
from aca.pricing import load_prices
from aca.sandbox import DEFAULT_IMAGE, build_image, make_sandbox
from aca.tasks import TASKS_ROOT, load_tasks, reference_code

app = typer.Typer(add_completion=False, no_args_is_help=True, help="Agent cost audit.")

PRICES_PATH = Path("config/prices.yaml")
RUN_PATH = Path("config/run.yaml")


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
