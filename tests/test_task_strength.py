"""Checks that the hidden tests are strong enough to mean something.

1. Planted bugs: each mutation puts one subtle bug into a reference solution. The task's hidden
   tests must fail on it. A test file that a plausible wrong answer passes is too weak.
2. The cron task's expected dates are checked against a brute-force oracle that steps one minute
   at a time and shares no code with the reference solution.
"""

from __future__ import annotations

import ast
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from aca.sandbox import SubprocessSandbox
from aca.tasks import reference_code

TASKS_ROOT = Path(__file__).resolve().parents[1] / "tasks"
SANDBOX = SubprocessSandbox(timeout_s=60)

# (task, text in the reference, replacement, the bug it plants)
MUTATIONS = [
    ("e1_interval_merge", "start <= merged[-1][1]", "start < merged[-1][1]",
     "touching intervals are not merged"),
    ("e2_lru_cache", "        self._items.move_to_end(key)\n        return value",
     "        return value", "get does not refresh recency"),
    ("e3_roman_numerals", "if not s or not _VALID.fullmatch(s):", "if not s:",
     "non-standard numerals are accepted"),
    ("m1_rate_limiter", "if now > self._last:", "if now != self._last:",
     "a clock going backwards removes tokens"),
    ("m1_rate_limiter", "now - used > max_idle_seconds", "now - used >= max_idle_seconds",
     "a key idle for exactly the limit is evicted"),
    ("m2_csv_validator", "row[position[name]].strip()", "row[position[name]]",
     "values are not stripped"),
    ("m2_csv_validator", "if row]", "]", "blank lines count as rows"),
    ("m3_tokenizer",
     "        if _is_digit(source, after_sign):\n            index = _digits(source, after_sign)",
     "        index = _digits(source, after_sign)", "an incomplete exponent is consumed"),
    ("m4_semver", "elif base.minor > 0:", "elif False:", "caret ranges are wrong below 1.0.0"),
    ("m4_semver",
     '(0, int(identifier), "") if identifier.isdigit() else (1, 0, identifier)',
     "(1, 0, identifier)", "numeric prerelease identifiers compare as strings"),
    ("h1_expr_eval", "return int(left < right)", "return left < right",
     "a comparison returns a bool"),
    ("h1_expr_eval", 'return ("binary", "**", base, self.unary())',
     'return ("binary", "**", base, self.primary())', "power is not right-associative"),
    ("h2_cron_next", "matches = day_matches or weekday_matches",
     "matches = day_matches and weekday_matches", "day of month AND day of week"),
    ("h2_cron_next", "candidate >= earliest", "candidate > earliest",
     "the first matching minute is skipped"),
    ("h3_spreadsheet",
     "            left = _as_number(self._evaluate(node[2], memo))\n"
     "            right = _as_number(self._evaluate(node[3], memo))",
     "            right = _as_number(self._evaluate(node[3], memo))\n"
     "            left = _as_number(self._evaluate(node[2], memo))",
     "operands are evaluated right to left"),
    ("h3_spreadsheet", "if value is not None and not isinstance(value, str):",
     "if value is not None:", "text cells in a range are not skipped"),
]  # fmt: skip


@pytest.mark.parametrize(
    ("task_id", "old", "new", "bug"), MUTATIONS, ids=[f"{m[0]}: {m[3]}" for m in MUTATIONS]
)
def test_hidden_tests_catch_a_planted_bug(task_id: str, old: str, new: str, bug: str) -> None:
    reference = reference_code(task_id, TASKS_ROOT)
    assert reference.count(old) == 1, "the mutation no longer matches the reference solution"
    tests = (TASKS_ROOT / task_id / "test_task.py").read_text(encoding="utf-8")
    result = SANDBOX.run(tests, reference.replace(old, new))
    assert not result.passed, f"hidden tests did not catch: {bug}"


# ---------- cron oracle ----------

_MONTHS = "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split()
_DAYS = "SUN MON TUE WED THU FRI SAT".split()


def _number(text: str, names: list[str], offset: int) -> int:
    return names.index(text.upper()) + offset if text.upper() in names else int(text)


def _expand(field: str, low: int, high: int, names=(), offset=0) -> set[int]:
    values: set[int] = set()
    for item in field.split(","):
        body, _, step = item.partition("/")
        step_size = int(step) if step else 1
        if body == "*":
            start, end = low, high
        elif "-" in body:
            start, end = (_number(part, list(names), offset) for part in body.split("-"))
        else:
            start = _number(body, list(names), offset)
            end = high if step else start
        values.update(range(start, end + 1, step_size))
    return values


def _oracle(expr: str, after: datetime) -> datetime | None:
    fields = expr.split()
    minutes, hours = _expand(fields[0], 0, 59), _expand(fields[1], 0, 23)
    doms, months = _expand(fields[2], 1, 31), _expand(fields[3], 1, 12, _MONTHS, 1)
    dows = {d % 7 for d in _expand(fields[4], 0, 7, _DAYS, 0)}
    moment = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    for _ in range(60 * 24 * 366 * 5):
        dom_ok, dow_ok = moment.day in doms, moment.isoweekday() % 7 in dows
        if fields[2] == "*" and fields[4] == "*":
            day_ok = True
        elif fields[2] == "*":
            day_ok = dow_ok
        elif fields[4] == "*":
            day_ok = dom_ok
        else:
            day_ok = dom_ok or dow_ok
        if day_ok and moment.month in months and moment.hour in hours and moment.minute in minutes:
            return moment
        moment += timedelta(minutes=1)
    return None


def _cron_cases() -> list[tuple[str, str, str]]:
    """Read CASES from the cron task's test file without importing it."""
    source = (TASKS_ROOT / "h2_cron_next" / "test_task.py").read_text(encoding="utf-8")
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == "CASES":
            return ast.literal_eval(node.value)
    raise AssertionError("CASES not found in the cron test file")


CRON_CASES = _cron_cases()


def test_cron_cases_are_numerous() -> None:
    assert len(CRON_CASES) >= 40


@pytest.mark.parametrize(("expr", "after", "expected"), CRON_CASES)
def test_cron_expectation_matches_the_brute_force_oracle(expr, after, expected) -> None:
    assert _oracle(expr, datetime.fromisoformat(after)) == datetime.fromisoformat(expected)
