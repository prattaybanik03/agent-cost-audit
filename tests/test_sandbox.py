from __future__ import annotations

import pytest

from aca.agent import Task
from aca.sandbox import (
    MAX_OUTPUT_CHARS,
    DockerSandbox,
    SandboxError,
    SubprocessSandbox,
    as_test_runner,
    docker_ready,
    make_sandbox,
    truncate,
)

SOLUTION = "def add(a, b):\n    return a + b\n"
TESTS = "from solution import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n"


@pytest.fixture(params=["subprocess", "docker"])
def sandbox(request):
    """Every behaviour test runs against both sandboxes. Docker is skipped when unavailable."""
    if request.param == "subprocess":
        return SubprocessSandbox(timeout_s=20)
    if not docker_ready():
        pytest.skip("Docker is not running or the sandbox image is not built")
    return DockerSandbox(timeout_s=20)


def test_correct_solution_passes(sandbox) -> None:
    result = sandbox.run(TESTS, SOLUTION)
    assert result.passed and not result.timed_out
    assert "1 passed" in result.output


def test_wrong_solution_fails_and_reports_the_assertion(sandbox) -> None:
    result = sandbox.run(TESTS, "def add(a, b):\n    return a - b\n")
    assert not result.passed and not result.timed_out
    assert "assert" in result.output


def test_syntax_error_in_the_solution_fails(sandbox) -> None:
    result = sandbox.run(TESTS, "def add(a, b:\n")
    assert not result.passed
    assert "SyntaxError" in result.output


def test_missing_name_fails(sandbox) -> None:
    result = sandbox.run(TESTS, "def something_else():\n    pass\n")
    assert not result.passed
    assert "ImportError" in result.output or "cannot import" in result.output


def test_no_tests_collected_is_not_a_pass(sandbox) -> None:
    assert not sandbox.run("# no tests here\n", SOLUTION).passed


def test_infinite_loop_times_out(sandbox) -> None:
    sandbox.timeout_s = 3
    result = sandbox.run(TESTS, "def add(a, b):\n    while True:\n        pass\n")
    assert not result.passed
    assert result.timed_out


def test_api_keys_are_not_visible_to_generated_code(sandbox, monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-not-a-real-key")
    monkeypatch.setenv("SOME_OTHER_SECRET", "hunter2")
    tests = (
        "import os\n\n\n"
        "def test_no_secrets():\n"
        "    assert 'ANTHROPIC_API_KEY' not in os.environ\n"
        "    assert 'SOME_OTHER_SECRET' not in os.environ\n"
    )
    result = sandbox.run(tests, "")
    assert result.passed, result.output


def test_long_output_is_truncated(sandbox) -> None:
    tests = "def test_noisy():\n    print('x' * 200_000)\n    assert False\n"
    result = sandbox.run(tests, "")
    assert not result.passed
    assert len(result.output) <= MAX_OUTPUT_CHARS + 100
    assert "truncated" in result.output


def test_docker_blocks_network_access() -> None:
    if not docker_ready():
        pytest.skip("Docker is not running or the sandbox image is not built")
    tests = (
        "import socket\n\n"
        "import pytest\n\n\n"
        "def test_cannot_reach_the_internet():\n"
        "    with pytest.raises(OSError):\n"
        "        socket.create_connection(('1.1.1.1', 53), timeout=3)\n"
    )
    result = DockerSandbox(timeout_s=20).run(tests, "")
    assert result.passed, result.output


def test_docker_filesystem_is_read_only() -> None:
    if not docker_ready():
        pytest.skip("Docker is not running or the sandbox image is not built")
    tests = (
        "import pytest\n\n\n"
        "def test_cannot_write_next_to_the_code():\n"
        "    with pytest.raises(OSError):\n"
        "        open('/work/dropped.txt', 'w').write('x')\n"
        "    with pytest.raises(OSError):\n"
        "        open('/etc/dropped.txt', 'w').write('x')\n"
    )
    result = DockerSandbox(timeout_s=20).run(tests, "")
    assert result.passed, result.output


def test_missing_image_is_a_sandbox_error_not_a_test_failure() -> None:
    if not docker_ready():
        pytest.skip("Docker is not running or the sandbox image is not built")
    sandbox = DockerSandbox(timeout_s=20, image="aca-sandbox:this-tag-does-not-exist")
    with pytest.raises(SandboxError):
        sandbox.run(TESTS, SOLUTION)


def test_truncate_keeps_the_start_and_the_end() -> None:
    short = "all good"
    assert truncate(short) == short
    long = "START" + "x" * 50_000 + "END"
    cut = truncate(long)
    assert cut.startswith("START") and cut.endswith("END")
    assert "truncated" in cut
    assert len(cut) <= MAX_OUTPUT_CHARS + 100


def test_only_docker_claims_network_isolation() -> None:
    assert SubprocessSandbox().isolates_network is False
    assert DockerSandbox().isolates_network is True


def test_make_sandbox_honours_an_explicit_choice() -> None:
    assert isinstance(make_sandbox("subprocess"), SubprocessSandbox)
    if docker_ready():
        assert isinstance(make_sandbox("docker"), DockerSandbox)
        assert isinstance(make_sandbox("auto"), DockerSandbox)


def test_test_runner_uses_the_tasks_hidden_tests() -> None:
    task = Task(task_id="add", prompt="Write add.", test_code=TESTS)
    run = as_test_runner(SubprocessSandbox(timeout_s=20))
    assert run(task, SOLUTION).passed
    assert not run(task, "def add(a, b):\n    return 0\n").passed
