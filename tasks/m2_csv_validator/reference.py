"""Reference solution. Never shown to a model."""

import csv
import io
import re
from dataclasses import dataclass
from datetime import date

_INT = re.compile(r"[+-]?[0-9]+")
_FLOAT = re.compile(r"[+-]?([0-9]+\.?[0-9]*|\.[0-9]+)([eE][+-]?[0-9]+)?")
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_BOOLS = {"true", "false", "1", "0", "yes", "no"}


@dataclass(frozen=True)
class CsvError:
    row: int
    column: str | None
    code: str
    message: str


def _measure(type_, value):
    """Return (valid, measure). The measure is what min and max compare, or None."""
    if type_ == "str":
        return True, len(value)
    if type_ == "int":
        return (True, int(value)) if _INT.fullmatch(value) else (False, None)
    if type_ == "float":
        return (True, float(value)) if _FLOAT.fullmatch(value) else (False, None)
    if type_ == "bool":
        return value.lower() in _BOOLS, None
    if type_ == "date":
        if not _DATE.fullmatch(value):
            return False, None
        try:
            date.fromisoformat(value)
        except ValueError:
            return False, None
        return True, None
    raise ValueError(f"unknown type {type_!r}")


def validate_csv(text, schema):
    if not text.strip():
        return [CsvError(1, None, "empty_file", "The file is empty.")]

    rows = [row for row in csv.reader(io.StringIO(text, newline="")) if row]
    header = [name.strip() for name in rows[0]]
    schema_names = [column["name"] for column in schema]
    errors = []

    for name in schema_names:
        if name not in header:
            errors.append(CsvError(1, name, "missing_column", f"Column {name!r} is missing."))
    seen = set()
    for name in header:
        if name in seen:
            errors.append(CsvError(1, name, "duplicate_column", f"Column {name!r} is repeated."))
        elif name not in schema_names:
            errors.append(CsvError(1, name, "unexpected_column", f"Column {name!r} is unexpected."))
        seen.add(name)

    position = {}
    for index, name in enumerate(header):
        position.setdefault(name, index)

    for number, row in enumerate(rows[1:], start=2):
        if len(row) != len(header):
            message = f"Expected {len(header)} fields but found {len(row)}."
            errors.append(CsvError(number, None, "field_count", message))
            continue
        for column in schema:
            name = column["name"]
            if name not in position:
                continue
            value = row[position[name]].strip()
            if value == "":
                if column.get("required", True):
                    errors.append(CsvError(number, name, "required", f"{name} is required."))
                continue
            valid, measure = _measure(column["type"], value)
            if not valid:
                message = f"{name}: {value!r} is not a valid {column['type']}."
                errors.append(CsvError(number, name, "type", message))
                continue
            if measure is not None and "min" in column and measure < column["min"]:
                message = f"{name}: {value!r} is below the minimum {column['min']}."
                errors.append(CsvError(number, name, "min", message))
            if measure is not None and "max" in column and measure > column["max"]:
                message = f"{name}: {value!r} is above the maximum {column['max']}."
                errors.append(CsvError(number, name, "max", message))
            if "choices" in column and value not in column["choices"]:
                message = f"{name}: {value!r} is not one of {column['choices']}."
                errors.append(CsvError(number, name, "choice", message))
    return errors
