# Spreadsheet with formulas and cycle detection

Write a Python module with a class `Sheet`: a small spreadsheet whose cells hold numbers, text or formulas. Do not use `eval`, `exec`, `compile` or the `ast` module.

## Cell names

A cell name is one upper-case letter `A` to `Z` followed by a row number from `1` to `999` with no leading zeros: `A1`, `C12`, `Z999`. Every method raises `ValueError` if given a name that is not exactly of this form (so `a1`, `A0`, `A01`, `AA1` and `A1000` are all rejected).

## Methods

### `set(cell, raw)`

Sets the cell's content.

- An `int` or `float` is stored as that number.
- A string that starts with `=` is a formula.
- The empty string `""` clears the cell.
- Any other string is stored as a number if it is written as one (`"42"` is the int `42`; `"-3.5"` and `"1e3"` are floats), and otherwise as text.

### `get(cell)`

Returns the cell's current value: an `int`, a `float`, a text string, `""` for an empty cell, or one of the error strings below. The value always reflects the current contents of every cell it depends on.

### `dependents(cell)`

Returns a list of the names of all cells whose formulas reference `cell` directly or through other cells. The list never includes `cell` itself. It is sorted by column letter, then by row number, so `A2` comes before `A10`, which comes before `B1`.

## Formulas

Whitespace is ignored. Cell references and function names may be written in either letter case.

- **Numbers**: digits with an optional decimal fraction, such as `12` or `3.5`.
- **Cell references**: `A1`.
- **Operators**: `+`, `-`, `*`, `/`, with the usual precedence, left-associative. Unary `-` and `+` are allowed and may be repeated.
- **Parentheses**.
- **Functions**: `SUM`, `MIN`, `MAX`, `AVG`, `COUNT`. Each takes one or more arguments separated by commas. An argument is either a range such as `A1:B3` or any expression. Functions can be nested.

Arithmetic:

- `+`, `-` and `*` give an `int` when both operands are ints. `/` always gives a `float`.
- An empty cell used as an operand counts as `0`.
- A formula that is just a reference returns that cell's value. If the cell holds text, the result is that text. If the cell is empty, the result is `0`.

Ranges and function arguments:

- A range covers the rectangle between its two corners, which may be given in any order. Its cells are read row by row from the top, and left to right within a row.
- An argument that is a single cell reference on its own, such as the `A1` in `SUM(A1, 5)`, is treated as a one-cell range.
- Within a range, empty cells and text cells are skipped. Only numbers are used.
- Any other argument is an expression and contributes its value.
- `SUM` adds the numbers (`0` if there are none). `MIN` and `MAX` give the smallest and largest (`0` if there are none). `COUNT` gives how many numbers there are. `AVG` is the sum divided by the count and is always a `float`.

## Errors

`get` returns an error string in these cases. The rules are applied in this order:

1. `#ERROR!`: the formula has a syntax error. This includes an empty formula (`=`), a range used outside a function argument, a function call with no arguments, and any character that is not part of the formula language.
2. `#CYCLE!`: the cell is part of a reference cycle, or depends directly or indirectly on a cell that is. This rule looks at every reference written in the formula, including the cells of its ranges, and it applies whatever else the formula contains. A formula with a syntax error has no references.
3. Otherwise the formula is evaluated by reading it from left to right, and the first error met is the result:

| Error | Cause |
| --- | --- |
| `#DIV/0!` | division by zero, or `AVG` with no numbers |
| `#VALUE!` | a text value used as an operand of `+`, `-`, `*`, `/` or unary minus |
| `#REF!` | a reference that looks like a cell (letters followed by digits) but is not a valid cell name, such as `A0`, `AA1` or `A1000`, on its own or as a corner of a range |
| `#NAME?` | a function name that is not one of the five, or a bare word that is not a function call. An unknown function is reported without evaluating its arguments. |
| any error | a referenced cell, or a cell in a range, whose own value is an error. That same error is the result. |

Left to right means an operand's error is raised before the next operand is looked at. If `A1` is `#DIV/0!` and `B1` holds text, then `=A1+B1` is `#DIV/0!` and `=B1+A1` is `#VALUE!`.

## Performance

`get` must not repeat work exponentially. A chain of 40 cells in which each formula references the previous cell twice must evaluate in well under a second.

## Requirements

- Put everything in one module. It will be saved as `solution.py` and imported by a pytest file you cannot see.
- Use only the Python standard library. The code runs on Python 3.12 with no network access.
- Use exactly the names and signatures above.
