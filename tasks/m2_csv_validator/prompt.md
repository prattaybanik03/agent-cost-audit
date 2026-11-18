# CSV validator with typed errors

Write a Python module that validates CSV text against a schema and reports every problem as a structured error.

## `CsvError`

A frozen dataclass with these fields, in this order:

| Field | Type | Meaning |
| --- | --- | --- |
| `row` | `int` | Row number. The header is row 1 and the first data row is row 2. |
| `column` | `str` or `None` | The column name, or `None` when the error is not about one column. |
| `code` | `str` | One of the codes below. |
| `message` | `str` | A non-empty human-readable description. |

## `validate_csv(text, schema)`

Returns a list of `CsvError`. An empty list means the text is valid.

`schema` is a list of column specs. Each is a dict:

| Key | Required | Meaning |
| --- | --- | --- |
| `name` | yes | Column name. |
| `type` | yes | `"str"`, `"int"`, `"float"`, `"bool"` or `"date"`. |
| `required` | no, default `True` | Whether an empty value is an error. |
| `min`, `max` | no | Inclusive bounds. |
| `choices` | no | A list of allowed strings. |

## Parsing

- Parse standard CSV: comma-separated, with double-quoted fields that may contain commas, line breaks and doubled quotes (`""`). Both `\n` and `\r\n` line endings are accepted.
- Rows are records, not physical lines. A quoted field containing a line break is still one row.
- Completely empty lines are ignored. They are not rows and do not advance the row number.
- The first row is the header. Header names and all values have leading and trailing whitespace removed before anything else is done with them.
- If the text is empty or contains only whitespace, return exactly one error: row `1`, column `None`, code `empty_file`.

## Header errors (all on row 1)

- `missing_column`: a schema column is absent from the header. `column` is its name. One error per missing column, in schema order.
- Then walk the header from left to right. A name that has already appeared earlier in the header gives `duplicate_column`. Otherwise, a name that is not in the schema gives `unexpected_column`. `column` is the name.

Validation continues after header errors. Columns that are missing are skipped in every row. Values in unexpected columns are ignored. When a name is duplicated, the first column with that name supplies the values.

## Row errors

For each data row, in order:

- If the number of fields differs from the number of header fields, report `field_count` with column `None` and do no other checks on that row.
- Otherwise check each schema column, in schema order:
  1. If the value is empty: report `required` if the column is required. Either way, do no further checks on that value.
  2. Check the type. If it fails, report `type` and do no further checks on that value.
  3. Check `min`, then `max`, then `choices`, reporting `min`, `max` and `choice`. A value can produce more than one of these.

## Types

- `str`: any text.
- `int`: an optional `+` or `-` followed by one or more digits. `"1.0"` is not an int.
- `float`: an optional sign, then digits with an optional decimal point (`"5"`, `"5."`, `".5"` and `"5.25"` are all valid), then an optional exponent such as `e3` or `E-2`. `nan`, `inf` and underscores such as `"1_000"` are not valid.
- `bool`: one of `true`, `false`, `1`, `0`, `yes`, `no`, in any letter case.
- `date`: exactly `YYYY-MM-DD` and a real calendar date. `"2024-02-30"` and `"2024-2-3"` are not valid.

## Bounds and choices

- For `int` and `float`, `min` and `max` compare the numeric value.
- For `str`, `min` and `max` compare the length of the text.
- For `bool` and `date`, `min` and `max` are ignored.
- `choices` applies to every type and compares the text exactly.

## Order of the returned list

Header errors first, in the order described above. Then row errors by row number, then by schema column order, then by check order.

## Requirements

- Put everything in one module. It will be saved as `solution.py` and imported by a pytest file you cannot see.
- Use only the Python standard library. The code runs on Python 3.12 with no network access.
- Use exactly the names and signatures above.
