"""Reference solution. Never shown to a model."""

from datetime import datetime, timedelta

_MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
_DAYS = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
_MONTH_NAMES = {name: index for index, name in enumerate(_MONTHS, start=1)}
_DAY_NAMES = {name: index for index, name in enumerate(_DAYS)}

# 29 February can be up to eight years away (2096 to 2104), so search a little further.
_SEARCH_DAYS = 366 * 9


class CronError(ValueError):
    pass


def _value(text, names):
    if text.isascii() and text.isdigit():
        return int(text)
    if text.upper() in names:
        return names[text.upper()]
    raise CronError(f"invalid value: {text!r}")


def _field(text, low, high, names):
    values = set()
    for item in text.split(","):
        base, slash, step_text = item.partition("/")
        step = 1
        if slash:
            if not (step_text.isascii() and step_text.isdigit()) or int(step_text) == 0:
                raise CronError(f"invalid step: {item!r}")
            step = int(step_text)
        if base == "*":
            start, end = low, high
        elif "-" in base:
            first, _, last = base.partition("-")
            start, end = _value(first, names), _value(last, names)
        else:
            start = _value(base, names)
            end = high if slash else start
        if not low <= start <= end <= high:
            raise CronError(f"value out of range: {item!r}")
        values.update(range(start, end + 1, step))
    return values


def _parse(expr):
    fields = expr.split()
    if len(fields) != 5:
        raise CronError("expected five fields")
    minutes = _field(fields[0], 0, 59, {})
    hours = _field(fields[1], 0, 23, {})
    days = _field(fields[2], 1, 31, {})
    months = _field(fields[3], 1, 12, _MONTH_NAMES)
    weekdays = {value % 7 for value in _field(fields[4], 0, 7, _DAY_NAMES)}
    return minutes, hours, days, months, weekdays, fields[2] == "*", fields[4] == "*"


def next_run(expr, after):
    minutes, hours, days, months, weekdays, any_day, any_weekday = _parse(expr)
    earliest = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    times = [(hour, minute) for hour in sorted(hours) for minute in sorted(minutes)]

    day = earliest.date()
    for _ in range(_SEARCH_DAYS):
        day_matches = day.day in days
        weekday_matches = day.isoweekday() % 7 in weekdays
        if any_day or any_weekday:
            matches = day_matches and weekday_matches
        else:
            matches = day_matches or weekday_matches
        if matches and day.month in months:
            for hour, minute in times:
                candidate = datetime(day.year, day.month, day.day, hour, minute)
                if candidate >= earliest:
                    return candidate
        day += timedelta(days=1)
    raise CronError("the expression never matches")


def next_runs(expr, after, n):
    runs = []
    for _ in range(n):
        after = next_run(expr, after)
        runs.append(after)
    return runs
