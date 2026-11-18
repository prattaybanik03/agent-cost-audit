import dataclasses

import pytest
from solution import Token, TokenizeError, tokenize


def kinds_and_text(source):
    return [(t.kind, t.text) for t in tokenize(source)]


def positions(source):
    return [(t.kind, t.line, t.col) for t in tokenize(source)]


def error_position(source):
    with pytest.raises(TokenizeError) as info:
        tokenize(source)
    return info.value.line, info.value.col


def test_token_is_a_frozen_dataclass():
    assert [f.name for f in dataclasses.fields(Token)] == ["kind", "text", "line", "col"]
    token = tokenize("x")[0]
    assert token == Token("IDENT", "x", 1, 1)
    with pytest.raises(dataclasses.FrozenInstanceError):
        token.col = 5


def test_tokenize_error_is_an_exception_with_a_position():
    assert issubclass(TokenizeError, Exception)
    assert error_position("@") == (1, 1)


def test_empty_source_is_just_eof():
    assert tokenize("") == [Token("EOF", "", 1, 1)]


def test_eof_position_follows_the_last_character():
    assert tokenize("ab")[-1] == Token("EOF", "", 1, 3)
    assert tokenize("ab\n")[-1] == Token("EOF", "", 2, 1)
    assert tokenize("ab  ")[-1] == Token("EOF", "", 1, 5)
    assert tokenize("a\n\n  ")[-1] == Token("EOF", "", 3, 3)


def test_simple_expression():
    assert kinds_and_text("total = price * (1 + rate)") == [
        ("IDENT", "total"),
        ("OP", "="),
        ("IDENT", "price"),
        ("OP", "*"),
        ("LPAREN", "("),
        ("NUMBER", "1"),
        ("OP", "+"),
        ("IDENT", "rate"),
        ("RPAREN", ")"),
        ("EOF", ""),
    ]


def test_columns_and_lines():
    assert positions("a + b\n  c") == [
        ("IDENT", 1, 1),
        ("OP", 1, 3),
        ("IDENT", 1, 5),
        ("IDENT", 2, 3),
        ("EOF", 2, 4),
    ]


def test_tab_and_carriage_return_each_advance_one_column():
    assert positions("\tx\r\n\ty") == [("IDENT", 1, 2), ("IDENT", 2, 2), ("EOF", 2, 3)]


def test_operators_use_the_longest_match():
    assert [t.text for t in tokenize("** == != <= >= && || + - * / % < > = !")][:-1] == [
        "**", "==", "!=", "<=", ">=", "&&", "||", "+", "-", "*", "/", "%", "<", ">", "=", "!",
    ]  # fmt: skip
    assert kinds_and_text("a**b")[1] == ("OP", "**")
    assert [t.text for t in tokenize("***")][:-1] == ["**", "*"]
    assert [t.text for t in tokenize("===")][:-1] == ["==", "="]
    assert [t.text for t in tokenize("!==")][:-1] == ["!=", "="]
    assert [t.text for t in tokenize("<==>")][:-1] == ["<=", "=", ">"]


def test_single_ampersand_and_pipe_are_errors():
    assert error_position("a & b") == (1, 3)
    assert error_position("a | b") == (1, 3)
    assert error_position("a &&& b") == (1, 5)


def test_identifiers():
    assert kinds_and_text("_x x1 snake_case CamelCase __")[:-1] == [
        ("IDENT", "_x"),
        ("IDENT", "x1"),
        ("IDENT", "snake_case"),
        ("IDENT", "CamelCase"),
        ("IDENT", "__"),
    ]


@pytest.mark.parametrize("text", ["0", "42", "3.14", ".5", "1e9", "1E9", "2.5e-3", ".5E+2", "007"])
def test_complete_numbers_are_one_token(text):
    assert kinds_and_text(text) == [("NUMBER", text), ("EOF", "")]


def test_number_stops_before_an_incomplete_part():
    assert kinds_and_text("1.5.2")[:-1] == [("NUMBER", "1.5"), ("NUMBER", ".2")]
    assert kinds_and_text("1e")[:-1] == [("NUMBER", "1"), ("IDENT", "e")]
    assert kinds_and_text("2e+x")[:-1] == [
        ("NUMBER", "2"),
        ("IDENT", "e"),
        ("OP", "+"),
        ("IDENT", "x"),
    ]
    assert kinds_and_text("3e-")[:-1] == [("NUMBER", "3"), ("IDENT", "e"), ("OP", "-")]
    assert kinds_and_text("4E5E6")[:-1] == [("NUMBER", "4E5"), ("IDENT", "E6")]
    assert kinds_and_text("12abc")[:-1] == [("NUMBER", "12"), ("IDENT", "abc")]


def test_dot_without_a_digit_is_an_error():
    assert error_position("1.") == (1, 2)
    assert error_position("1..2") == (1, 2)
    assert error_position("x = .") == (1, 5)
    assert error_position("1.e3") == (1, 2)


def test_number_followed_by_operator_and_number():
    assert kinds_and_text("1-2")[:-1] == [("NUMBER", "1"), ("OP", "-"), ("NUMBER", "2")]
    assert kinds_and_text("1e-2-3")[:-1] == [("NUMBER", "1e-2"), ("OP", "-"), ("NUMBER", "3")]


def test_strings_are_decoded():
    assert kinds_and_text('"hello"')[0] == ("STRING", "hello")
    assert kinds_and_text('""')[0] == ("STRING", "")
    assert kinds_and_text(r'"a\"b"')[0] == ("STRING", 'a"b')
    assert kinds_and_text(r'"a\\b"')[0] == ("STRING", "a\\b")
    assert kinds_and_text(r'"line\nnext\tend"')[0] == ("STRING", "line\nnext\tend")
    assert kinds_and_text('"# not a comment"')[0] == ("STRING", "# not a comment")


def test_string_position_and_following_token():
    assert tokenize('x = "ab" y') == [
        Token("IDENT", "x", 1, 1),
        Token("OP", "=", 1, 3),
        Token("STRING", "ab", 1, 5),
        Token("IDENT", "y", 1, 10),
        Token("EOF", "", 1, 11),
    ]


def test_unknown_escape_is_reported_at_the_backslash():
    assert error_position(r'"ab\qcd"') == (1, 4)
    assert error_position('x\n  "\\x41"') == (2, 4)


def test_unterminated_string_is_reported_at_the_opening_quote():
    assert error_position('  "abc') == (1, 3)
    assert error_position('a = "abc\n"') == (1, 5)
    assert error_position('"') == (1, 1)


def test_comments_are_skipped():
    source = "a # first\n# whole line\n  b # last"
    assert positions(source) == [("IDENT", 1, 1), ("IDENT", 3, 3), ("EOF", 3, 11)]
    assert kinds_and_text("# only a comment") == [("EOF", "")]


def test_function_call_with_commas():
    assert [t.kind for t in tokenize("max(a, 2.5, f(x))")] == [
        "IDENT", "LPAREN", "IDENT", "COMMA", "NUMBER", "COMMA", "IDENT", "LPAREN", "IDENT",
        "RPAREN", "RPAREN", "EOF",
    ]  # fmt: skip


@pytest.mark.parametrize(
    ("source", "where"),
    [("a $ b", (1, 3)), ("x\ny ? z", (2, 3)), ("[1]", (1, 1)), ("a;", (1, 2)), ("'s'", (1, 1))],
)
def test_unexpected_characters(source, where):
    assert error_position(source) == where
