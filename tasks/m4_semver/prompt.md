# Semantic version parsing and ranges

Write a Python module that parses, compares and matches semantic versions, following Semantic Versioning 2.0.0.

## Version format

A version is `MAJOR.MINOR.PATCH`, optionally followed by `-PRERELEASE`, optionally followed by `+BUILD`.

- `MAJOR`, `MINOR` and `PATCH` are non-negative integers with no leading zeros (`0` is fine, `01` is not).
- `PRERELEASE` and `BUILD` are each one or more identifiers separated by dots. An identifier is one or more of the characters `0-9`, `A-Z`, `a-z` and `-`. An empty identifier is invalid.
- A prerelease identifier made only of digits must not have a leading zero. Build identifiers may.
- Nothing else is allowed: no leading `v`, no whitespace, no missing parts.

## `Version`

A frozen dataclass with these fields, in this order: `major` (int), `minor` (int), `patch` (int), `prerelease` (tuple of str), `build` (tuple of str). The tuples are empty when that part is absent.

## Functions

### `parse(version)`

Returns a `Version`. Raises `ValueError` if the string is not a valid version.

### `compare(a, b)`

Takes two version strings. Returns `-1` if `a` has lower precedence than `b`, `1` if higher, and `0` if equal. Precedence:

1. Compare `major`, then `minor`, then `patch`, numerically.
2. If those are equal, a version with a prerelease is lower than one without.
3. If both have a prerelease, compare identifiers from left to right:
   - two numeric identifiers compare numerically
   - two non-numeric identifiers compare as ASCII strings
   - a numeric identifier is lower than a non-numeric one
   - if all shared identifiers are equal, the version with fewer identifiers is lower
4. Build metadata is ignored.

### `sort_versions(versions)`

Takes a list of version strings and returns a new list in ascending precedence. Versions of equal precedence keep their original relative order.

### `bump(version, part)`

`part` is `"major"`, `"minor"` or `"patch"`. Returns a version string with that part increased by one, the lower parts reset to `0`, and any prerelease and build removed. `bump("1.2.3-alpha+7", "patch")` is `"1.2.4"`. Raises `ValueError` for any other `part`.

### `satisfies(version, range_spec)`

Returns `True` if the version matches the range. A range is one or more comparators separated by spaces, and the version must match all of them. A comparator is one of:

| Form | Matches versions `v` where |
| --- | --- |
| `1.2.3` or `=1.2.3` | `v` equals `1.2.3` in precedence |
| `>1.2.3`, `>=1.2.3`, `<1.2.3`, `<=1.2.3` | the comparison holds in precedence |
| `~1.2.3` | `1.2.3 <= v < 1.3.0` |
| `^1.2.3` | `1.2.3 <= v < 2.0.0` |
| `^0.2.3` | `0.2.3 <= v < 0.3.0` |
| `^0.0.3` | `0.0.3 <= v < 0.0.4` |

The version inside a comparator may have a prerelease, such as `>=1.0.0-rc.1`.

Matching uses precedence only, with no special treatment of prereleases. So `2.0.0-alpha` satisfies `^1.2.3`, because `2.0.0-alpha` is lower than `2.0.0`.

Raises `ValueError` if `version` is invalid, or if the range is empty or contains an invalid comparator.

## Requirements

- Put everything in one module. It will be saved as `solution.py` and imported by a pytest file you cannot see.
- Use only the Python standard library. The code runs on Python 3.12 with no network access.
- Use exactly the names and signatures above.
