import pytest
from solution import Sheet


def make(**cells):
    sheet = Sheet()
    for name, raw in cells.items():
        sheet.set(name, raw)
    return sheet


def value_of(formula, **cells):
    sheet = make(**cells)
    sheet.set("Z999", formula)
    return sheet.get("Z999")


def check(formula, expected, **cells):
    result = value_of(formula, **cells)
    assert type(result) is type(expected), (formula, result)
    assert result == pytest.approx(expected) if isinstance(expected, float) else result == expected


DATA = {"A1": 1, "A2": 2, "A3": "x", "B1": 10, "B2": 20.5}  # A4 is empty


def test_plain_values():
    sheet = make(A1=5, B1=2.5, C1="hello")
    assert sheet.get("A1") == 5 and type(sheet.get("A1")) is int
    assert sheet.get("B1") == 2.5 and type(sheet.get("B1")) is float
    assert sheet.get("C1") == "hello"
    assert sheet.get("D9") == ""


def test_numeric_strings_become_numbers():
    sheet = make(A1="42", A2="-3.5", A3="1e3", A4="abc", A5="12abc", A6="+7")
    assert sheet.get("A1") == 42 and type(sheet.get("A1")) is int
    assert sheet.get("A2") == -3.5 and type(sheet.get("A2")) is float
    assert sheet.get("A3") == 1000.0 and type(sheet.get("A3")) is float
    assert sheet.get("A4") == "abc"
    assert sheet.get("A5") == "12abc"
    assert sheet.get("A6") == 7


def test_empty_string_clears_a_cell():
    sheet = make(A1=5, B1="=A1+1")
    sheet.set("A1", "")
    assert sheet.get("A1") == ""
    assert sheet.get("B1") == 1


@pytest.mark.parametrize(
    ("formula", "expected"),
    [("=1+2*3", 7), ("=(1+2)*3", 9), ("=-4+10", 6), ("=10/4", 2.5), ("=4/2", 2.0),
     ("=2*3.5", 7.0), ("= 1 +  2 ", 3), ("=--3", 3), ("=-(2+3)", -5), ("=2-3-4", -5),
     ("=24/4/2", 3.0), ("=1.5+1.5", 3.0), ("=+5", 5), ("=2*-3", -6), ("=7", 7), ("=0.5", 0.5)],
)  # fmt: skip
def test_arithmetic(formula, expected):
    check(formula, expected)


def test_references_and_recalculation():
    sheet = make(A1=2, B1="=A1*10", C1="=B1+A1")
    assert sheet.get("B1") == 20
    assert sheet.get("C1") == 22
    sheet.set("A1", 3)
    assert sheet.get("B1") == 30
    assert sheet.get("C1") == 33
    sheet.set("B1", 100)
    assert sheet.get("C1") == 103


def test_references_and_functions_are_case_insensitive():
    check("=a1+sum(a1:b2)+Max(b1,B2)", 55.0, **DATA)


def test_empty_cells_count_as_zero():
    check("=C9+1", 1)
    check("=C9", 0)
    check("=C9*5", 0)


def test_text_cells():
    assert value_of("=A3", **DATA) == "x"
    assert value_of("=A3+1", **DATA) == "#VALUE!"
    assert value_of("=1+A3", **DATA) == "#VALUE!"
    assert value_of("=-A3", **DATA) == "#VALUE!"
    assert value_of("=A3*A3", **DATA) == "#VALUE!"


def test_division_by_zero_and_propagation():
    sheet = make(A1="=1/0", B1="=A1+1", C1="=SUM(B1,2)", D1="=5/E9", E1="=0/5")
    assert sheet.get("A1") == "#DIV/0!"
    assert sheet.get("B1") == "#DIV/0!"
    assert sheet.get("C1") == "#DIV/0!"
    assert sheet.get("D1") == "#DIV/0!"
    assert sheet.get("E1") == 0.0


def test_first_error_from_left_to_right_wins():
    cells = {"A1": "=1/0", "B1": "text"}
    assert value_of("=A1+B1", **cells) == "#DIV/0!"
    assert value_of("=B1+A1", **cells) == "#VALUE!"
    assert value_of("=B1*2+A1", **cells) == "#VALUE!"
    assert value_of("=1/0+NOPE(1)", **cells) == "#DIV/0!"
    assert value_of("=NOPE(1)+1/0", **cells) == "#NAME?"


@pytest.mark.parametrize(
    ("formula", "expected"),
    [("=SUM(A1:A4)", 3), ("=SUM(A1:B2)", 33.5), ("=SUM(B2:A1)", 33.5), ("=SUM(B1:A2)", 33.5),
     ("=SUM(A1,B1,5)", 16), ("=SUM(A3)", 0), ("=SUM(A4:A4)", 0), ("=SUM(A1:A2,B1:B2,100)", 133.5),
     ("=SUM(A1:A2)*2", 6), ("=SUM(A1+A2,1)", 4), ("=COUNT(A1:A4)", 2), ("=COUNT(A1:B2,7)", 5),
     ("=COUNT(A3:A4)", 0), ("=MIN(A1:B2)", 1), ("=MAX(A1:B2)", 20.5), ("=MIN(A3:A4)", 0),
     ("=MAX(A4)", 0), ("=AVG(A1:A2)", 1.5), ("=AVG(B1:B1)", 10.0), ("=AVG(A1:A4)", 1.5),
     ("=SUM(MAX(A1:A2),MIN(B1:B2))", 12), ("=MAX(1,2)+MIN(3,4)*2", 8),
     ("=SUM(1,2,3)/COUNT(1,2,3)", 2.0), ("=MAX(-5,-2)", -2), ("=SUM(A1:A1)", 1)],
)  # fmt: skip
def test_functions_and_ranges(formula, expected):
    check(formula, expected, **DATA)


def test_text_in_an_expression_argument_is_an_error_but_in_a_range_it_is_skipped():
    assert value_of("=SUM(A3)", **DATA) == 0
    assert value_of("=SUM(A3:A3)", **DATA) == 0
    assert value_of("=SUM(A3+1)", **DATA) == "#VALUE!"
    assert value_of("=SUM(A1,A3*2)", **DATA) == "#VALUE!"


def test_avg_of_no_numbers_is_div_zero():
    assert value_of("=AVG(A3:A4)", **DATA) == "#DIV/0!"
    assert value_of("=AVG(A4)", **DATA) == "#DIV/0!"


def test_formula_cells_inside_a_range_are_evaluated():
    sheet = make(A1=1, B1=10, C1="=A1+B1", D1="=SUM(A1:C1)", E1="=COUNT(A1:D1)")
    assert sheet.get("D1") == 22
    assert sheet.get("E1") == 4


def test_error_inside_a_range_propagates():
    cells = {"A1": 1, "A2": "=1/0", "A3": 3}
    assert value_of("=SUM(A1:A3)", **cells) == "#DIV/0!"
    assert value_of("=COUNT(A1:A3)", **cells) == "#DIV/0!"
    assert value_of("=MAX(A2)", **cells) == "#DIV/0!"


@pytest.mark.parametrize(
    "formula", ["=FOO(1)", "=FOO", "=FOO(1/0)", "=SUMM(A1:A2)", "=X+1", "=1+pi"]
)
def test_unknown_names(formula):
    assert value_of(formula, **DATA) == "#NAME?"


@pytest.mark.parametrize(
    "formula",
    ["=A0", "=AA1", "=A1000", "=A01", "=A1+A0", "=SUM(A1:A0)", "=SUM(A0:A2)", "=SUM(AB1)", "=-B0"],
)
def test_invalid_references(formula):
    assert value_of(formula, **DATA) == "#REF!"


def test_last_valid_cell_is_a_real_reference():
    assert value_of("=Y999+1") == 1


@pytest.mark.parametrize(
    "formula",
    ["=", "=   ", "=1+", "=(1", "=1)", "=1 2", "=1+*2", "=SUM()", "=A1:A2", "=$A1", "=SUM(A1:)",
     "=SUM(A1:5)", "=SUM(1,)", "=SUM(,1)", "=A1 A2", "=2(3)", "=SUM(A1:A2:A3)", "=1+A1:A2",
     "=SUM A1", "=#", "=1,2", "=*2", "=(A1:A2)"],
)  # fmt: skip
def test_syntax_errors(formula):
    assert value_of(formula, **DATA) == "#ERROR!"


def test_reference_to_a_syntax_error_cell_propagates():
    sheet = make(A1="=1+", B1="=A1+1", C1="=SUM(A1:A2)")
    assert sheet.get("A1") == "#ERROR!"
    assert sheet.get("B1") == "#ERROR!"
    assert sheet.get("C1") == "#ERROR!"


def test_self_reference_is_a_cycle():
    sheet = make(A1="=A1", B1="=B1+1", C1="=SUM(C1:C3)")
    assert sheet.get("A1") == "#CYCLE!"
    assert sheet.get("B1") == "#CYCLE!"
    assert sheet.get("C1") == "#CYCLE!"


def test_cycle_members_and_their_dependents():
    sheet = make(A1="=B1", B1="=C1+1", C1="=A1*2", D1="=A1+5", E1="=SUM(D1:D2)", F1="=5")
    for name in ("A1", "B1", "C1", "D1", "E1"):
        assert sheet.get(name) == "#CYCLE!", name
    assert sheet.get("F1") == 5


def test_cycle_takes_priority_over_other_errors():
    sheet = make(A1="=1/0+A1", B1="=NOPE(B1)", C1="=A0+C1", D1="text", E1="=D1+E1")
    for name in ("A1", "B1", "C1", "E1"):
        assert sheet.get(name) == "#CYCLE!", name


def test_syntax_error_takes_priority_over_a_cycle():
    sheet = make(A1="=A1+", B1="=A1")
    assert sheet.get("A1") == "#ERROR!"
    assert sheet.get("B1") == "#ERROR!"


def test_breaking_a_cycle_restores_values():
    sheet = make(A1="=B1", B1="=A1+1", C1="=A1*2")
    assert sheet.get("C1") == "#CYCLE!"
    sheet.set("B1", 4)
    assert sheet.get("A1") == 4
    assert sheet.get("C1") == 8
    sheet.set("B1", "=C1")
    assert sheet.get("A1") == "#CYCLE!"
    sheet.set("C1", "")
    assert sheet.get("A1") == 0


def test_dependents_are_transitive_and_sorted():
    sheet = make(A1=1, B1="=A1+1", C1="=B1*2", D1="=SUM(A1:A3)", A10="=A1", A2="=a1", E1="=7")
    assert sheet.dependents("A1") == ["A2", "A10", "B1", "C1", "D1"]
    assert sheet.dependents("B1") == ["C1"]
    assert sheet.dependents("C1") == []
    assert sheet.dependents("A3") == ["D1"]
    assert sheet.dependents("Z1") == []


def test_dependents_follow_changes():
    sheet = make(A1=1, B1="=A1+1", C1="=B1*2")
    sheet.set("B1", 5)
    assert sheet.dependents("A1") == []
    assert sheet.dependents("B1") == ["C1"]
    sheet.set("C1", "")
    assert sheet.dependents("B1") == []


def test_dependents_in_a_cycle_exclude_the_cell_itself():
    sheet = make(A1="=B1", B1="=A1", C1="=C1", D1="=A1")
    assert sheet.dependents("A1") == ["B1", "D1"]
    assert sheet.dependents("C1") == []


@pytest.mark.parametrize(
    "name", ["a1", "A0", "A01", "AA1", "A1000", "1A", "", "A", "A-1", " A1", "A1 "]
)
def test_invalid_cell_names_are_rejected(name):
    sheet = Sheet()
    with pytest.raises(ValueError):
        sheet.set(name, 1)
    with pytest.raises(ValueError):
        sheet.get(name)
    with pytest.raises(ValueError):
        sheet.dependents(name)


def test_long_chain():
    sheet = Sheet()
    sheet.set("A1", 1)
    for row in range(2, 61):
        sheet.set(f"A{row}", f"=A{row - 1}+1")
    assert sheet.get("A60") == 60
    assert len(sheet.dependents("A1")) == 59


def test_shared_references_are_not_recomputed_exponentially():
    sheet = Sheet()
    sheet.set("A1", 1)
    for row in range(2, 41):
        sheet.set(f"A{row}", f"=A{row - 1}+A{row - 1}")
    assert sheet.get("A40") == 2**39
    sheet.set("A1", "=A40")
    assert sheet.get("A40") == "#CYCLE!"
