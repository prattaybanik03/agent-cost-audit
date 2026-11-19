"""Runs untrusted, model-generated code against a task's hidden tests.

Two sandboxes share one interface:

- `DockerSandbox` runs each test in a fresh container with no network, a read-only filesystem,
  no capabilities, and memory, CPU and process limits. This is the one real runs should use.
- `SubprocessSandbox` runs pytest in a child process with a timeout, a temp directory and a
  stripped environment. It does NOT block network access, and it does NOT isolate the file
  system: generated code runs as the current user and can read any file that user can,
  including a project's .env, by absolute path. It exists for machines without Docker. Do not
  use it with real secrets on the machine.

A run counts as passed only if pytest exits 0 AND its summary reports at least one passed test
and no failures or errors. The exit code alone is not trusted: code that calls os._exit(0) at
import would otherwise pass without a single test running.

A sandbox failure (Docker not running, image missing) raises `SandboxError`. It is never
reported as a failed test, because that would blame the model for an infrastructure fault.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Literal, Protocol

from aca.agent import Task, TestResult, TestRunner

DEFAULT_IMAGE = "aca-sandbox:py312"
DEFAULT_TIMEOUT_S = 30.0
MAX_OUTPUT_CHARS = 6000
_HEAD_CHARS = 3500
PYTEST_ARGS = ["-q", "--tb=short", "-p", "no:cacheprovider", "test_task.py"]

# Environment variables the subprocess sandbox passes through. Everything else, including any
# API key, is withheld from generated code.
_ENV_ALLOWLIST = ("PATH", "SYSTEMROOT", "SystemRoot", "TEMP", "TMP", "TMPDIR", "LANG")

# `docker run` exit codes that mean Docker itself failed, not the command inside the container.
_DOCKER_FAILURE_CODES = {125, 126, 127}
_KILLED = 137


class SandboxError(RuntimeError):
    """The sandbox could not run the tests at all."""


class Sandbox(Protocol):
    name: str
    isolates_network: bool

    def run(self, test_code: str, solution_code: str) -> TestResult: ...


_COUNTS = re.compile(r"(\d+) (passed|failed|error|errors)\b")
_SKIPPED = re.compile(r"\b\d+ (skipped|xfailed|xpassed|deselected)\b")


def pytest_counts(output: str) -> tuple[int, int]:
    """(passed, failed) from pytest's summary line. Errors count as failures."""
    passed = failed = 0
    for number, word in _COUNTS.findall(output):
        if word == "passed":
            passed = int(number)
        else:
            failed += int(number)
    return passed, failed


def judge(returncode: int, output: str) -> TestResult:
    """A pass needs exit code 0 and a pytest summary with passes, no failures, and no skipped or
    deselected tests. The hidden tests never skip, so a skip means the code under test caused it
    (for example by calling pytest.skip), and that is not a pass."""
    passed, failed = pytest_counts(output)
    ok = returncode == 0 and passed > 0 and failed == 0 and not _SKIPPED.search(output)
    return TestResult(passed=ok, output=truncate(output))


def truncate(output: str) -> str:
    """Keep the start and end of long test output so a fix prompt stays a bounded size."""
    if len(output) <= MAX_OUTPUT_CHARS:
        return output
    tail = MAX_OUTPUT_CHARS - _HEAD_CHARS
    return output[:_HEAD_CHARS] + "\n... [test output truncated] ...\n" + output[-tail:]


def _write_workdir(root: Path, test_code: str, solution_code: str) -> None:
    (root / "solution.py").write_text(solution_code, encoding="utf-8")
    (root / "test_task.py").write_text(test_code, encoding="utf-8")


class SubprocessSandbox:
    name = "subprocess"
    isolates_network = False

    def __init__(self, timeout_s: float = DEFAULT_TIMEOUT_S, python: str = sys.executable) -> None:
        self.timeout_s = timeout_s
        self.python = python

    def run(self, test_code: str, solution_code: str) -> TestResult:
        env = {key: os.environ[key] for key in _ENV_ALLOWLIST if key in os.environ}
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        with tempfile.TemporaryDirectory(prefix="aca-", ignore_cleanup_errors=True) as tmp:
            _write_workdir(Path(tmp), test_code, solution_code)
            try:
                proc = subprocess.run(
                    [self.python, "-m", "pytest", *PYTEST_ARGS],
                    cwd=tmp,
                    env=env,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=self.timeout_s,
                )
            except subprocess.TimeoutExpired:
                return TestResult(
                    passed=False,
                    output=f"Tests did not finish within {self.timeout_s:g} seconds.",
                    timed_out=True,
                )
        return judge(proc.returncode, proc.stdout + proc.stderr)


class DockerSandbox:
    name = "docker"
    isolates_network = True

    def __init__(
        self,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        image: str = DEFAULT_IMAGE,
        startup_allowance_s: float = 30.0,
    ) -> None:
        self.timeout_s = timeout_s
        self.image = image
        self.startup_allowance_s = startup_allowance_s

    def run(self, test_code: str, solution_code: str) -> TestResult:
        name = f"aca-{uuid.uuid4().hex[:12]}"
        limit = str(max(1, int(self.timeout_s)))
        with tempfile.TemporaryDirectory(prefix="aca-", ignore_cleanup_errors=True) as tmp:
            _write_workdir(Path(tmp), test_code, solution_code)
            command = [
                "docker", "run", "--rm", "--name", name,
                "--network", "none",
                "--read-only", "--tmpfs", "/tmp:rw,size=64m",
                "--memory", "512m", "--cpus", "1", "--pids-limit", "128",
                "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                "--user", "65534:65534",
                "-e", "PYTHONDONTWRITEBYTECODE=1",
                "-v", f"{tmp}:/work:ro", "-w", "/work",
                self.image,
                "timeout", "-s", "KILL", limit,
                "python", "-m", "pytest", *PYTEST_ARGS,
            ]  # fmt: skip
            try:
                proc = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=self.timeout_s + self.startup_allowance_s,
                )
            except subprocess.TimeoutExpired:
                subprocess.run(["docker", "kill", name], capture_output=True, check=False)
                return self._timed_out()
            except FileNotFoundError as exc:
                raise SandboxError("The docker command was not found.") from exc

        if proc.returncode in _DOCKER_FAILURE_CODES:
            raise SandboxError(f"docker run failed ({proc.returncode}): {proc.stderr.strip()}")
        if proc.returncode == _KILLED:
            return self._timed_out()
        return judge(proc.returncode, proc.stdout + proc.stderr)

    def _timed_out(self) -> TestResult:
        return TestResult(
            passed=False,
            output=(
                f"Tests were killed: they did not finish within {self.timeout_s:g} seconds "
                "or exceeded the memory limit."
            ),
            timed_out=True,
        )


def docker_ready(image: str = DEFAULT_IMAGE) -> bool:
    """True if the Docker daemon answers and the sandbox image exists."""
    try:
        proc = subprocess.run(
            ["docker", "image", "inspect", image], capture_output=True, check=False, timeout=30
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


def build_image(dockerfile_dir: str | Path, image: str = DEFAULT_IMAGE) -> None:
    proc = subprocess.run(
        ["docker", "build", "-t", image, str(dockerfile_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SandboxError(f"docker build failed: {proc.stderr.strip()}")


SandboxKind = Literal["auto", "docker", "subprocess"]


def make_sandbox(kind: SandboxKind = "auto", timeout_s: float = DEFAULT_TIMEOUT_S) -> Sandbox:
    """Pick a sandbox. "auto" uses Docker when it is ready and falls back to a subprocess."""
    if kind == "subprocess":
        return SubprocessSandbox(timeout_s)
    if docker_ready():
        return DockerSandbox(timeout_s)
    if kind == "docker":
        raise SandboxError(
            f"Docker is not running or the image {DEFAULT_IMAGE} is missing. "
            "Start Docker and run `aca sandbox-build`."
        )
    return SubprocessSandbox(timeout_s)


def as_test_runner(sandbox: Sandbox) -> TestRunner:
    """Adapt a sandbox to the test-runner callable the agent loop takes."""

    def run(task: Task, code: str) -> TestResult:
        return sandbox.run(task.test_code, code)

    return run
