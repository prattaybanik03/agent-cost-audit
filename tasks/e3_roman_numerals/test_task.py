import pytest
from solution import from_roman, to_roman

KNOWN = [
    (1, "I"),
    (2, "II"),
    (3, "III"),
    (4, "IV"),
    (5, "V"),
    (9, "IX"),
    (14, "XIV"),
    (40, "XL"),
    (49, "XLIX"),
    (90, "XC"),
    (99, "XCIX"),
    (400, "CD"),
    (444, "CDXLIV"),
    (900, "CM"),
    (1994, "MCMXCIV"),
    (2024, "MMXXIV"),
    (3888, "MMMDCCCLXXXVIII"),
    (3999, "MMMCMXCIX"),
]


@pytest.mark.parametrize(("number", "numeral"), KNOWN)
def test_to_roman_known_values(number, numeral):
    assert to_roman(number) == numeral


@pytest.mark.parametrize(("number", "numeral"), KNOWN)
def test_from_roman_known_values(number, numeral):
    assert from_roman(numeral) == number


def test_round_trip_for_every_number():
    for number in range(1, 4000):
        assert from_roman(to_roman(number)) == number


def test_numerals_are_unique():
    assert len({to_roman(number) for number in range(1, 4000)}) == 3999


@pytest.mark.parametrize("number", [0, -1, 4000, 10_000])
def test_to_roman_rejects_out_of_range(number):
    with pytest.raises(ValueError):
        to_roman(number)


@pytest.mark.parametrize("value", [True, False, 3.0, "3", None])
def test_to_roman_rejects_non_ints(value):
    with pytest.raises(TypeError):
        to_roman(value)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "iv",
        "Iv",
        "IIII",
        "VV",
        "LL",
        "DD",
        "XXXX",
        "CCCC",
        "MMMM",
        "IC",
        "IL",
        "VX",
        "XD",
        "IIV",
        "IXI",
        "IVI",
        "XCX",
        "CMC",
        "IXIV",
        "A",
        "X1",
        " X",
        "X ",
        "MCMXCIVI",
    ],
)
def test_from_roman_rejects_non_standard_forms(text):
    with pytest.raises(ValueError):
        from_roman(text)


@pytest.mark.parametrize("value", [4, None, ["X"], b"X"])
def test_from_roman_rejects_non_strings(value):
    with pytest.raises(TypeError):
        from_roman(value)
