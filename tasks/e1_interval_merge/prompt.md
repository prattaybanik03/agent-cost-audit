# Interval merging

Write a Python module that works with closed integer intervals.

An interval is a tuple `(start, end)` of two ints with `start <= end`. It covers every point from `start` to `end` inclusive.

## Functions

### `merge_intervals(intervals)`

Takes a list of intervals in any order. Returns a new list of tuples in which intervals that overlap or touch have been merged, sorted by start.

- Two intervals touch when one ends exactly where the other starts: `(1, 3)` and `(3, 5)` merge into `(1, 5)`.
- `(1, 2)` and `(3, 4)` share no point, so they stay separate.
- The input list must not be modified.
- An empty list returns an empty list.

### `insert_interval(intervals, new)`

Returns the merged result of `intervals` plus the single interval `new`. `intervals` may be unsorted and may itself contain overlaps. The input list must not be modified.

### `total_covered(intervals)`

Returns the total length covered: the sum of `end - start` over the merged intervals. `[(1, 4), (2, 6)]` gives `5`. An interval with `start == end` has length `0`.

## Errors

All three functions raise `ValueError` if any interval, including `new`, has `start > end`.

## Requirements

- Put everything in one module. It will be saved as `solution.py` and imported by a pytest file you cannot see.
- Use only the Python standard library. The code runs on Python 3.12 with no network access.
- Use exactly the names and signatures above.
