# Next run time for a cron expression

Write a Python module that works out when a cron schedule next fires. All datetimes are naive `datetime.datetime` objects. There are no time zones.

## `CronError`

An exception class that is a subclass of `ValueError`.

## `next_run(expr, after)`

Returns the earliest datetime that is strictly later than `after` and matches the cron expression `expr`. The result always has `second == 0` and `microsecond == 0`.

"Strictly later" compares full datetimes. With `* * * * *`, both `10:00:00` and `10:00:30` give `10:01:00`.

## `next_runs(expr, after, n)`

Returns a list of the next `n` matching datetimes in order. Each one is the `next_run` after the one before. `n == 0` gives an empty list.

## Expression format

Five fields separated by one or more spaces or tabs. Leading and trailing whitespace is ignored.

| Field | Allowed values | Names |
| --- | --- | --- |
| minute | 0-59 | |
| hour | 0-23 | |
| day of month | 1-31 | |
| month | 1-12 | `JAN` to `DEC` |
| day of week | 0-7, where both 0 and 7 mean Sunday | `SUN` to `SAT` (`SUN` is 0) |

Names are three letters, in any letter case, and can be used anywhere a number can in their field.

Each field is a comma-separated list of one or more items. An item is one of:

| Item | Meaning |
| --- | --- |
| `*` | every allowed value |
| `N` | the single value `N` |
| `A-B` | every value from `A` to `B` inclusive |
| `*/S` | every `S`th value, starting from the lowest allowed value |
| `A-B/S` | every `S`th value from `A` to `B`, starting at `A` |
| `A/S` | every `S`th value from `A` to the highest allowed value, starting at `A` |

## Matching

A datetime matches when its minute, hour and month are in their fields and its day matches. The day rule depends on the day-of-month and day-of-week fields:

- If both fields are exactly `*`, every day matches.
- If exactly one of them is exactly `*`, the day must match the other field.
- If neither is exactly `*`, the day matches when it matches **either** field.

A field such as `*/2` is not exactly `*`.

## Errors

Raise `CronError` when:

- there are not exactly five fields
- an item is empty or malformed, such as `1,,2`, `a`, `1-`, `*/x` or `1-2-3`
- a value is outside the allowed range for its field
- a range has `A > B`
- a step is `0`
- the expression can never match any date, such as `0 0 30 2 *`

## Requirements

- Put everything in one module. It will be saved as `solution.py` and imported by a pytest file you cannot see.
- Use only the Python standard library. The code runs on Python 3.12 with no network access.
- Use exactly the names and signatures above.
