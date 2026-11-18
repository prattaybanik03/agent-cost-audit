"""Reference solution. Never shown to a model."""


def merge_intervals(intervals):
    for start, end in intervals:
        if start > end:
            raise ValueError(f"interval start {start} is after end {end}")
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def insert_interval(intervals, new):
    return merge_intervals([*intervals, new])


def total_covered(intervals):
    return sum(end - start for start, end in merge_intervals(intervals))
