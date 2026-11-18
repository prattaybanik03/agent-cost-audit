import math

import pytest
from solution import EvalError, ExprError, ParseError, evaluate


def check(expression, expected, variables=None):
    result = evaluate(expression, variables)
    assert type(result) is type(expected), (expression, result)
    if isinstance(expected, float):
        assert result == pytest.approx(expected), expression
    else:
        assert result == expected, expression


def parse_error_position(expression):
    with pytest.raises(ParseError) as info:
        evaluate(expression)
    return info.value.position


def test_exception_hierarchy():
    assert issubclass(ExprError, Exception)
    assert issubclass(ParseError, ExprError)
    assert issubclass(EvalError, ExprError)


@pytest.mark.parametrize(
    ("expression", "expected"),
    [("12", 12), ("0", 0), ("3.5", 3.5), (".5", 0.5), ("1e3", 1000.0), ("2.5e-2", 0.025),
     ("7.0", 7.0), ("1E2", 100.0)],
)  # fmt: skip
def test_number_literals(expression, expected):
    check(expression, expected)


@pytest.mark.parametrize(
    ("expression", "expected"),
    [("1 + 2", 3), ("5 - 8", -3), ("4 * 6", 24), ("7 / 2", 3.5), ("4 / 2", 2.0),
     ("7 // 2", 3), ("7 % 3", 1), ("2 ** 10", 1024), ("1.5 + 1.5", 3.0), ("2 * 0.5", 1.0),
     ("7.0 // 2", 3.0), ("7.5 % 2", 1.5)],
)  # fmt: skip
def test_binary_operators_and_result_types(expression, expected):
    check(expression, expected)


@pytest.mark.parametrize(
    ("expression", "expected"),
    [("-7 // 2", -4), ("7 // -2", -4), ("-7 % 3", 2), ("7 % -3", -2), ("-7.5 // 2", -4.0)],
)
def test_floor_division_and_modulo_round_toward_negative_infinity(expression, expected):
    check(expression, expected)


@pytest.mark.parametrize(
    ("expression", "expected"),
    [("2 + 3 * 4", 14), ("2 * 3 + 4 * 5", 26), ("10 - 4 - 3", 3), ("100 / 10 / 5", 2.0),
     ("2 * 3 % 4", 2), ("8 // 3 * 3", 6), ("(2 + 3) * 4", 20), ("((7))", 7),
     ("2 * (3 + (4 - 1)) * 2", 24)],
)  # fmt: skip
def test_precedence_and_associativity(expression, expected):
    check(expression, expected)


@pytest.mark.parametrize(
    ("expression", "expected"),
    [("2 ** 3 ** 2", 512), ("-2 ** 2", -4), ("(-2) ** 2", 4), ("2 ** -1", 0.5),
     ("2 ** -2 ** 2", 0.0625), ("-2 ** -2", -0.25), ("2 * 3 ** 2", 18), ("2 ** 0.5", math.sqrt(2)),
     ("4 ** 0.5", 2.0), ("2.0 ** 3", 8.0), ("10 ** -1 * 10", 1.0)],
)  # fmt: skip
def test_power(expression, expected):
    check(expression, expected)


@pytest.mark.parametrize(
    ("expression", "expected"),
    [("-3", -3), ("+3", 3), ("--3", 3), ("-+-3", 3), ("- - - 3", -3), ("4 - -3", 7),
     ("4 * -3", -12), ("-(2 + 3)", -5), ("-2.5", -2.5)],
)  # fmt: skip
def test_unary_operators(expression, expected):
    check(expression, expected)


@pytest.mark.parametrize(
    ("expression", "expected"),
    [("3 > 2", 1), ("3 < 2", 0), ("2 <= 2", 1), ("2 >= 3", 0), ("2 == 2.0", 1), ("2 != 2", 0),
     ("1 + 1 == 2", 1), ("2 * 3 > 5 + 0", 1), ("(1 < 2) + (2 < 3)", 2), ("(1 < 2) < 3", 1)],
)  # fmt: skip
def test_comparisons_give_int_one_or_zero(expression, expected):
    check(expression, expected)


@pytest.mark.parametrize(
    ("expression", "expected"),
    [("1 ? 10 : 20", 10), ("0 ? 10 : 20", 20), ("0.0 ? 10 : 20", 20), ("-1 ? 10 : 20", 10),
     ("3 > 2 ? 1 + 1 : 9", 2), ("0 ? 1 : 0 ? 2 : 3", 3), ("1 ? 0 ? 5 : 6 : 7", 6),
     ("1 ? 2 : 3 + 100", 2), ("(0 ? 2 : 3) + 100", 103), ("1 ? 2.5 : 3", 2.5)],
)  # fmt: skip
def test_conditional(expression, expected):
    check(expression, expected)


def test_conditional_evaluates_only_the_chosen_branch():
    check("1 ? 2 : 1 / 0", 2)
    check("0 ? 1 / 0 : 3", 3)
    check("1 ? 2 : missing", 2)
    check("0 ? sqrt(-1) : 4", 4)
    with pytest.raises(EvalError):
        evaluate("0 ? 2 : 1 / 0")


def test_variables():
    values = {"x": 3, "rate": 0.5, "_tmp1": 10}
    check("x * 2", 6, values)
    check("x * rate", 1.5, values)
    check("_tmp1 - x", 7, values)
    check("x ** 2 + x", 12, values)
    check("-x", -3, values)


@pytest.mark.parametrize(
    ("expression", "expected"),
    [("abs(-3)", 3), ("abs(2.5)", 2.5), ("min(3, 1, 2)", 1), ("max(3, 1, 2)", 3), ("min(7)", 7),
     ("max(1, 2.5)", 2.5), ("sqrt(16)", 4.0), ("sqrt(2.25)", 1.5), ("round(2.4)", 2),
     ("round(2.6)", 3), ("round(-2.6)", -3), ("round(3.14159, 2)", 3.14),
     ("max(1, min(5, 10)) * 2", 10), ("abs(min(-1, -2) * 3)", 6), ("sqrt(abs(-9)) + 1", 4.0),
     ("round(7)", 7)],
)  # fmt: skip
def test_functions(expression, expected):
    check(expression, expected)


def test_whitespace_is_ignored():
    check("  1+2  ", 3)
    check("\t2\n*\n3 ", 6)
    check("max( 1 ,2 )", 2)
    check("2**3", 8)
    check("7//2", 3)


@pytest.mark.parametrize(
    "expression", ["1 / 0", "1 // 0", "1 % 0", "0 ** -1", "5 / (2 - 2)", "1.5 % 0"]
)
def test_division_by_zero(expression):
    with pytest.raises(EvalError, match="division by zero"):
        evaluate(expression)


def test_unknown_variable_names_the_variable():
    with pytest.raises(EvalError, match="speed"):
        evaluate("speed * 2")
    with pytest.raises(EvalError, match="y"):
        evaluate("x + y", {"x": 1})


@pytest.mark.parametrize(
    "expression",
    ["nope(1)", "abs()", "abs(1, 2)", "sqrt(1, 2)", "min()", "max()", "round()", "round(1, 2, 3)",
     "sqrt(-4)", "(-8) ** 0.5", "round(2.5, 1.5)"],
)  # fmt: skip
def test_other_evaluation_errors(expression):
    with pytest.raises(EvalError):
        evaluate(expression)


@pytest.mark.parametrize(
    ("expression", "position"),
    [("", 0), ("1 +", 3), ("1 + * 2", 4), ("(1 + 2", 6), ("1 2", 2), ("1 + $", 4), (")", 0),
     ("1 < 2 < 3", 6), ("1 == 2 != 3", 7), ("1 ? 2", 5), ("1 ? 2 :", 7), ("1 : 2", 2),
     ("min(1,)", 6), ("min(1 2)", 6), ("max(1, 2", 8), ("2 ** ", 5), ("* 3", 0), ("a b", 2),
     ("3 + (4 * )", 9), ("1 +\n  ?", 6), ("4 4.5", 2), ("()", 1), ("abs(,1)", 4)],
)  # fmt: skip
def test_parse_error_positions(expression, position):
    assert parse_error_position(expression) == position


def test_syntax_errors_win_even_in_a_branch_that_would_not_run():
    assert parse_error_position("1 ? 2 : (") == 9
    assert parse_error_position("0 ? ) : 3") == 4
    with pytest.raises(ParseError):
        evaluate("1 / 0 +")


def test_errors_share_a_base_class():
    for expression in ("1 +", "1 / 0", "nope"):
        with pytest.raises(ExprError):
            evaluate(expression)


def test_variables_argument_is_optional_and_not_modified():
    values = {"x": 2}
    assert evaluate("x + 1", values) == 3
    assert values == {"x": 2}
    assert evaluate("1 + 1") == 2
    assert evaluate("1 + 1", None) == 2
