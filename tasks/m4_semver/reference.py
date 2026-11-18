"""Reference solution. Never shown to a model."""

import re
from dataclasses import dataclass

_NUMBER = r"(0|[1-9][0-9]*)"
_VERSION = re.compile(
    rf"{_NUMBER}\.{_NUMBER}\.{_NUMBER}(?:-([0-9A-Za-z.-]+))?(?:\+([0-9A-Za-z.-]+))?"
)
_COMPARATOR = re.compile(r"(\^|~|>=|<=|>|<|=)?(.+)")


@dataclass(frozen=True)
class Version:
    major: int
    minor: int
    patch: int
    prerelease: tuple
    build: tuple


def parse(version):
    match = _VERSION.fullmatch(version) if isinstance(version, str) else None
    if match is None:
        raise ValueError(f"invalid version: {version!r}")
    prerelease = tuple(match[4].split(".")) if match[4] else ()
    build = tuple(match[5].split(".")) if match[5] else ()
    if any(identifier == "" for identifier in prerelease + build):
        raise ValueError(f"empty identifier in version: {version!r}")
    for identifier in prerelease:
        if identifier.isdigit() and len(identifier) > 1 and identifier[0] == "0":
            raise ValueError(f"leading zero in prerelease identifier: {version!r}")
    return Version(int(match[1]), int(match[2]), int(match[3]), prerelease, build)


def _key(parsed):
    if not parsed.prerelease:
        prerelease_key = (1,)
    else:
        identifiers = tuple(
            (0, int(identifier), "") if identifier.isdigit() else (1, 0, identifier)
            for identifier in parsed.prerelease
        )
        prerelease_key = (0, identifiers)
    return (parsed.major, parsed.minor, parsed.patch, prerelease_key)


def compare(a, b):
    key_a = _key(parse(a))
    key_b = _key(parse(b))
    return (key_a > key_b) - (key_a < key_b)


def sort_versions(versions):
    return sorted(versions, key=lambda version: _key(parse(version)))


def bump(version, part):
    parsed = parse(version)
    if part == "major":
        return f"{parsed.major + 1}.0.0"
    if part == "minor":
        return f"{parsed.major}.{parsed.minor + 1}.0"
    if part == "patch":
        return f"{parsed.major}.{parsed.minor}.{parsed.patch + 1}"
    raise ValueError(f"unknown part: {part!r}")


def _bounds(comparator):
    """Return a list of (operator, version key) pairs the version must satisfy."""
    match = _COMPARATOR.fullmatch(comparator)
    operator = match[1] or "="
    base = parse(match[2])
    key = _key(base)
    if operator == "~":
        upper = (base.major, base.minor + 1, 0, (1,))
        return [(">=", key), ("<", upper)]
    if operator == "^":
        if base.major > 0:
            upper = (base.major + 1, 0, 0, (1,))
        elif base.minor > 0:
            upper = (0, base.minor + 1, 0, (1,))
        else:
            upper = (0, 0, base.patch + 1, (1,))
        return [(">=", key), ("<", upper)]
    return [(operator, key)]


def _holds(operator, key, bound):
    if operator == "=":
        return key == bound
    if operator == ">":
        return key > bound
    if operator == ">=":
        return key >= bound
    if operator == "<":
        return key < bound
    return key <= bound


def satisfies(version, range_spec):
    key = _key(parse(version))
    comparators = range_spec.split()
    if not comparators:
        raise ValueError("empty range")
    bounds = [bound for comparator in comparators for bound in _bounds(comparator)]
    return all(_holds(operator, key, bound) for operator, bound in bounds)
