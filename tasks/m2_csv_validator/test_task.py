import dataclasses

import pytest
from solution import CsvError, validate_csv

SCHEMA = [
    {"name": "id", "type": "int", "min": 1},
    {"name": "name", "type": "str", "min": 2, "max": 10},
    {"name": "score", "type": "float", "required": False, "min": 0, "max": 100},
    {"name": "active", "type": "bool"},
    {"name": "joined", "type": "date", "required": False},
    {"name": "tier", "type": "str", "choices": ["free", "pro"]},
]
HEADER = "id,name,score,active,joined,tier\n"


def codes(text, schema=SCHEMA):
    return [(e.row, e.column, e.code) for e in validate_csv(text, schema)]


def test_valid_file_has_no_errors():
    text = HEADER + "1,Ada,99.5,true,2024-02-29,pro\n2,Bob,,no,,free\n"
    assert validate_csv(text, SCHEMA) == []


def test_header_only_is_valid():
    assert validate_csv(HEADER, SCHEMA) == []


@pytest.mark.parametrize("text", ["", "   ", "\n\n", " \r\n\t\n"])
def test_empty_file(text):
    assert codes(text) == [(1, None, "empty_file")]


def test_error_is_a_frozen_dataclass_with_a_message():
    errors = validate_csv(HEADER + "x,Ada,1,true,,pro\n", SCHEMA)
    assert len(errors) == 1
    error = errors[0]
    assert isinstance(error, CsvError)
    assert [f.name for f in dataclasses.fields(CsvError)] == ["row", "column", "code", "message"]
    assert isinstance(error.message, str) and error.message.strip()
    with pytest.raises(dataclasses.FrozenInstanceError):
        error.row = 99


def test_missing_columns_are_reported_in_schema_order():
    text = "name,active\nAda,true\n"
    assert codes(text) == [
        (1, "id", "missing_column"),
        (1, "score", "missing_column"),
        (1, "joined", "missing_column"),
        (1, "tier", "missing_column"),
    ]


def test_rows_are_still_checked_when_columns_are_missing():
    text = "name,active\nA,maybe\n"
    assert codes(text)[4:] == [(2, "name", "min"), (2, "active", "type")]


def test_unexpected_and_duplicate_columns():
    text = "id,notes,name,score,active,joined,tier,id\n1,hello,Ada,5,yes,,pro,oops\n"
    assert codes(text) == [(1, "notes", "unexpected_column"), (1, "id", "duplicate_column")]


def test_missing_errors_come_before_unexpected_ones():
    schema = [{"name": "a", "type": "int"}, {"name": "b", "type": "int"}]
    assert codes("zzz,a\n1,2\n", schema) == [
        (1, "b", "missing_column"),
        (1, "zzz", "unexpected_column"),
    ]


def test_wrong_field_count_skips_other_checks_on_that_row():
    text = HEADER + "x,Ada\n1,Ada,5,true,,pro,extra\n0,Ada,5,true,,pro\n"
    assert codes(text) == [
        (2, None, "field_count"),
        (3, None, "field_count"),
        (4, "id", "min"),
    ]


def test_required_and_optional_empty_values():
    text = HEADER + ",,,,,\n"
    assert codes(text) == [
        (2, "id", "required"),
        (2, "name", "required"),
        (2, "active", "required"),
        (2, "tier", "required"),
    ]


@pytest.mark.parametrize(
    ("value", "valid"),
    [("7", True), ("+7", True), ("-7", True), ("007", True), ("1.0", False), ("1e3", False),
     ("seven", False), ("1_000", False), ("--1", False), ("1 2", False)],
)  # fmt: skip
def test_int_type(value, valid):
    result = codes(f"n\n{value}\n", [{"name": "n", "type": "int"}])
    assert result == ([] if valid else [(2, "n", "type")])


@pytest.mark.parametrize(
    ("value", "valid"),
    [("5", True), ("5.", True), (".5", True), ("-5.25", True), ("+1e3", True), ("2.5E-2", True),
     ("nan", False), ("inf", False), ("-inf", False), ("1_000", False), ("1e", False),
     (".", False), ("abc", False), ("1.2.3", False)],
)  # fmt: skip
def test_float_type(value, valid):
    result = codes(f"n\n{value}\n", [{"name": "n", "type": "float"}])
    assert result == ([] if valid else [(2, "n", "type")])


@pytest.mark.parametrize(
    ("value", "valid"),
    [("true", True), ("FALSE", True), ("Yes", True), ("no", True), ("1", True), ("0", True),
     ("y", False), ("2", False), ("t", False), ("on", False)],
)  # fmt: skip
def test_bool_type(value, valid):
    result = codes(f"n\n{value}\n", [{"name": "n", "type": "bool"}])
    assert result == ([] if valid else [(2, "n", "type")])


@pytest.mark.parametrize(
    ("value", "valid"),
    [("2024-02-29", True), ("1999-12-31", True), ("2023-02-29", False), ("2024-02-30", False),
     ("2024-2-3", False), ("2024/02/03", False), ("20240203", False), ("2024-13-01", False),
     ("2024-02-03T00:00", False)],
)  # fmt: skip
def test_date_type(value, valid):
    result = codes(f"n\n{value}\n", [{"name": "n", "type": "date"}])
    assert result == ([] if valid else [(2, "n", "type")])


def test_numeric_bounds_are_inclusive():
    schema = [{"name": "n", "type": "float", "min": 0, "max": 100}]
    text = "n\n0\n100\n-0.5\n100.5\n1e3\n"
    assert codes(text, schema) == [(4, "n", "min"), (5, "n", "max"), (6, "n", "max")]


def test_string_bounds_use_length():
    schema = [{"name": "s", "type": "str", "min": 2, "max": 4}]
    text = "s\nab\nabcd\na\nabcde\n"
    assert codes(text, schema) == [(4, "s", "min"), (5, "s", "max")]


def test_bounds_are_ignored_for_bool_and_date():
    schema = [
        {"name": "b", "type": "bool", "min": 5, "max": 6},
        {"name": "d", "type": "date", "min": 5, "max": 6},
    ]
    assert codes("b,d\ntrue,2024-01-01\n", schema) == []


def test_choices_compare_text_exactly():
    schema = [{"name": "tier", "type": "str", "choices": ["free", "pro"]}]
    assert codes("tier\nfree\nPro\npro \nteam\n", schema) == [
        (3, "tier", "choice"),
        (5, "tier", "choice"),
    ]


def test_choices_apply_to_other_types():
    schema = [{"name": "n", "type": "int", "choices": ["1", "2"]}]
    assert codes("n\n1\n3\n01\n", schema) == [(3, "n", "choice"), (4, "n", "choice")]


def test_one_value_can_fail_bounds_and_choices():
    schema = [{"name": "n", "type": "int", "min": 5, "max": 3, "choices": ["1"]}]
    assert codes("n\n4\n", schema) == [(2, "n", "min"), (2, "n", "max"), (2, "n", "choice")]


def test_type_failure_stops_further_checks_on_that_value():
    schema = [{"name": "n", "type": "int", "min": 5, "choices": ["9"]}]
    assert codes("n\nabc\n", schema) == [(2, "n", "type")]


def test_errors_are_ordered_by_row_then_schema_column():
    text = HEADER + "0,A,101,maybe,2024-99-99,gold\n" + "1,Ada,5,true,,pro\n" + "x,Bo,-1,1,,free\n"
    assert codes(text) == [
        (2, "id", "min"),
        (2, "name", "min"),
        (2, "score", "max"),
        (2, "active", "type"),
        (2, "joined", "type"),
        (2, "tier", "choice"),
        (4, "id", "type"),
        (4, "score", "min"),
    ]


def test_schema_order_wins_over_header_order():
    schema = [{"name": "a", "type": "int"}, {"name": "b", "type": "int"}]
    assert codes("b,a\nx,y\n", schema) == [(2, "a", "type"), (2, "b", "type")]


def test_quoted_fields_with_commas_quotes_and_line_breaks():
    schema = [{"name": "id", "type": "int"}, {"name": "note", "type": "str", "max": 20}]
    text = (
        'id,note\n1,"a, b"\n2,"line one\nline two"\n3,"say ""hi"""\n'
        'x,"this note is far too long, yes"\n'
    )
    assert codes(text, schema) == [(5, "id", "type"), (5, "note", "max")]


def test_blank_lines_do_not_advance_the_row_number():
    schema = [{"name": "n", "type": "int"}]
    assert codes("\nn\n\n1\n\n\nx\n", schema) == [(3, "n", "type")]


def test_whitespace_is_stripped_from_header_names_and_values():
    schema = [{"name": "n", "type": "int"}, {"name": "s", "type": "str", "choices": ["ok"]}]
    assert codes(" n , s \n  7 ,  ok  \n   ,ok\n", schema) == [(3, "n", "required")]


def test_crlf_line_endings():
    schema = [{"name": "n", "type": "int"}]
    assert codes("n\r\n1\r\nx\r\n", schema) == [(3, "n", "type")]


def test_duplicate_column_uses_the_first_occurrence():
    schema = [{"name": "n", "type": "int"}]
    assert codes("n,n\n1,x\ny,2\n", schema) == [(1, "n", "duplicate_column"), (3, "n", "type")]
