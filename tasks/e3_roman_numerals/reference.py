"""Reference solution. Never shown to a model."""

import re

_PAIRS = [
    (1000, "M"),
    (900, "CM"),
    (500, "D"),
    (400, "CD"),
    (100, "C"),
    (90, "XC"),
    (50, "L"),
    (40, "XL"),
    (10, "X"),
    (9, "IX"),
    (5, "V"),
    (4, "IV"),
    (1, "I"),
]
_VALID = re.compile(r"M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})")


def to_roman(n):
    if isinstance(n, bool) or not isinstance(n, int):
        raise TypeError("n must be an int")
    if not 1 <= n <= 3999:
        raise ValueError("n must be between 1 and 3999")
    parts = []
    for value, numeral in _PAIRS:
        count, n = divmod(n, value)
        parts.append(numeral * count)
    return "".join(parts)


def from_roman(s):
    if not isinstance(s, str):
        raise TypeError("s must be a str")
    if not s or not _VALID.fullmatch(s):
        raise ValueError(f"not a standard Roman numeral: {s!r}")
    total = 0
    position = 0
    for value, numeral in _PAIRS:
        while s.startswith(numeral, position):
            total += value
            position += len(numeral)
    return total
