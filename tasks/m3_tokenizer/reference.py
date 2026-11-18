"""Reference solution. Never shown to a model."""

from dataclasses import dataclass

_TWO_CHAR_OPS = ("**", "==", "!=", "<=", ">=", "&&", "||")
_ONE_CHAR_OPS = "+-*/%<>=!"
_PUNCTUATION = {"(": "LPAREN", ")": "RPAREN", ",": "COMMA"}
_ESCAPES = {'"': '"', "\\": "\\", "n": "\n", "t": "\t"}
_DIGITS = "0123456789"


@dataclass(frozen=True)
class Token:
    kind: str
    text: str
    line: int
    col: int


class TokenizeError(Exception):
    def __init__(self, message, line, col):
        super().__init__(f"{message} at line {line}, column {col}")
        self.line = line
        self.col = col


def _is_ident_start(char):
    return char.isascii() and (char.isalpha() or char == "_")


def _is_ident_part(char):
    return char.isascii() and (char.isalnum() or char == "_")


def _is_digit(source, index):
    return index < len(source) and source[index] in _DIGITS


def _digits(source, index):
    while _is_digit(source, index):
        index += 1
    return index


def _number_end(source, index):
    """Index just past the number starting at `index`. Optional parts must be complete."""
    if source[index] == ".":
        index = _digits(source, index + 1)
    else:
        index = _digits(source, index)
        if index < len(source) and source[index] == "." and _is_digit(source, index + 1):
            index = _digits(source, index + 1)
    if index < len(source) and source[index] in "eE":
        after_sign = index + 1
        if after_sign < len(source) and source[after_sign] in "+-":
            after_sign += 1
        if _is_digit(source, after_sign):
            index = _digits(source, after_sign)
    return index


def tokenize(source):
    tokens = []
    index = 0
    line = 1
    col = 1
    length = len(source)

    while index < length:
        char = source[index]

        if char == "\n":
            index += 1
            line += 1
            col = 1
            continue
        if char in " \t\r":
            index += 1
            col += 1
            continue
        if char == "#":
            while index < length and source[index] != "\n":
                index += 1
                col += 1
            continue

        if char in _DIGITS or (char == "." and _is_digit(source, index + 1)):
            end = _number_end(source, index)
            tokens.append(Token("NUMBER", source[index:end], line, col))
            col += end - index
            index = end
            continue

        if _is_ident_start(char):
            end = index + 1
            while end < length and _is_ident_part(source[end]):
                end += 1
            tokens.append(Token("IDENT", source[index:end], line, col))
            col += end - index
            index = end
            continue

        if char == '"':
            start_col = col
            parts = []
            index += 1
            col += 1
            while True:
                if index >= length or source[index] == "\n":
                    raise TokenizeError("unterminated string", line, start_col)
                current = source[index]
                if current == '"':
                    index += 1
                    col += 1
                    break
                if current == "\\":
                    following = source[index + 1] if index + 1 < length else ""
                    if following == "" or following == "\n":
                        raise TokenizeError("unterminated string", line, start_col)
                    if following not in _ESCAPES:
                        raise TokenizeError("unknown escape", line, col)
                    parts.append(_ESCAPES[following])
                    index += 2
                    col += 2
                    continue
                parts.append(current)
                index += 1
                col += 1
            tokens.append(Token("STRING", "".join(parts), line, start_col))
            continue

        pair = source[index : index + 2]
        if pair in _TWO_CHAR_OPS:
            tokens.append(Token("OP", pair, line, col))
            index += 2
            col += 2
            continue
        if char in _ONE_CHAR_OPS:
            tokens.append(Token("OP", char, line, col))
            index += 1
            col += 1
            continue
        if char in _PUNCTUATION:
            tokens.append(Token(_PUNCTUATION[char], char, line, col))
            index += 1
            col += 1
            continue

        raise TokenizeError(f"unexpected character {char!r}", line, col)

    tokens.append(Token("EOF", "", line, col))
    return tokens
