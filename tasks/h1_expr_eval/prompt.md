# Expression parser and evaluator

Write a Python module that parses and evaluates arithmetic expressions. Do not use `eval`, `exec`, `compile` or the `ast` module.

## `evaluate(expression, variables=None)`

`expression` is a string. `variables` is an optional dict mapping names to ints or floats. Returns an `int` or a `float`.

## Exceptions

- `ExprError`: a subclass of `Exception`, and the base class of the two below.
- `ParseError`: the expression is not well formed. It has an integer attribute `position`: the 0-based index in `expression` of the first character of the token that is wrong. When the expression ends too early, `position` is `len(expression)`.
- `EvalError`: the expression is well formed but cannot be evaluated.

The whole expression is parsed before anything is evaluated, so a syntax error anywhere always raises `ParseError`.

## Syntax

Whitespace between tokens is ignored.

- **Numbers.** Digits with an optional fraction and an optional exponent: `12`, `3.5`, `.5`, `1e3`, `2.5e-2`. A number written with only digits is an `int`. A number with a `.` or an exponent is a `float`.
- **Names.** A letter or `_`, then letters, digits or `_`. A name is a variable, unless it is followed by `(`, in which case it is a function call.
- **Operators**, from lowest to highest precedence:

| Level | Operators | Notes |
| --- | --- | --- |
| 1 | `c ? a : b` | Conditional. Right-associative. |
| 2 | `<` `<=` `>` `>=` `==` `!=` | Not associative: `1 < 2 < 3` is a `ParseError` at the second operator. |
| 3 | `+` `-` | Left-associative. |
| 4 | `*` `/` `//` `%` | Left-associative. |
| 5 | unary `+` `-` | May be repeated: `--3` is `3`. |
| 6 | `**` | Right-associative. Binds tighter than a unary operator on its left and looser than one on its right. |

So `-2 ** 2` is `-4`, `2 ** -1` is `0.5`, and `2 ** 3 ** 2` is `512`.

- **Parentheses** group as usual.
- **Function calls**: `name(arg, arg, ...)`, with arguments separated by commas.

## Semantics

Arithmetic follows Python's rules for ints and floats:

- `+`, `-`, `*`, `//`, `%` and `**` give an `int` when both operands are ints, except that `**` with a negative int exponent gives a `float`.
- `/` always gives a `float`.
- `//` and `%` round toward negative infinity, as in Python: `-7 // 2` is `-4` and `-7 % 3` is `2`.
- Comparisons give the int `1` or `0`, never a `bool`.
- The conditional `c ? a : b` evaluates `c`. If it is non-zero the result is `a`, otherwise `b`. Only the chosen branch is evaluated, so `1 ? 2 : 1 / 0` is `2`.

Functions:

| Function | Result |
| --- | --- |
| `abs(x)` | absolute value |
| `min(a, b, ...)`, `max(a, b, ...)` | smallest or largest of one or more arguments |
| `sqrt(x)` | square root, always a `float` |
| `round(x)` | nearest int, as Python's `round(x)` |
| `round(x, n)` | `x` rounded to `n` decimal places, as Python's `round(x, n)`. `n` must be an int. |

Raise `EvalError` for:

- division, floor division or modulo by zero, and zero raised to a negative power. The message must contain `division by zero`.
- a variable that is not in `variables`. The message must contain the variable's name.
- a function that is not in the table, or a call with the wrong number of arguments
- `sqrt` of a negative number
- a power whose result is not a real number, such as `(-8) ** 0.5`
- `round(x, n)` where `n` is not an int

These errors are raised only if the offending part is actually evaluated.

## Requirements

- Put everything in one module. It will be saved as `solution.py` and imported by a pytest file you cannot see.
- Use only the Python standard library. The code runs on Python 3.12 with no network access.
- Use exactly the names and signatures above.
