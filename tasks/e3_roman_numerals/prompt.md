# Roman numerals with strict validation

Write a Python module that converts between integers and Roman numerals.

## Functions

### `to_roman(n)`

Returns the standard Roman numeral for the integer `n`, in upper case, using subtractive notation (`4` is `IV`, `9` is `IX`, `40` is `XL`, `90` is `XC`, `400` is `CD`, `900` is `CM`).

- Raise `ValueError` if `n` is outside `1` to `3999` inclusive.
- Raise `TypeError` if `n` is not an `int`. A `bool` is not accepted, and neither is a float such as `3.0`.

### `from_roman(s)`

Returns the integer for the Roman numeral `s`.

Validation is strict. `s` is accepted only if it is exactly the numeral `to_roman` would produce for some number from `1` to `3999`. Everything else raises `ValueError`, including:

- the empty string
- lower-case or mixed-case input such as `"iv"`
- non-standard forms such as `"IIII"`, `"VV"`, `"IC"`, `"VX"`, `"IIV"` and `"MMMM"`
- surrounding whitespace such as `" X"`

Raise `TypeError` if `s` is not a `str`.

## Requirements

- Put everything in one module. It will be saved as `solution.py` and imported by a pytest file you cannot see.
- Use only the Python standard library. The code runs on Python 3.12 with no network access.
- Use exactly the names and signatures above.
