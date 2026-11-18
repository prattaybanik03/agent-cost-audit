# Tokenizer for a small expression language

Write a Python module that turns source text into a list of tokens with positions.

## `Token`

A frozen dataclass with these fields, in this order: `kind` (str), `text` (str), `line` (int), `col` (int).

`line` and `col` are 1-based and give the position of the token's first character. Every character, including a tab, advances `col` by 1. A newline (`\n`) starts a new line and resets `col` to 1.

## `TokenizeError`

An exception class (a subclass of `Exception`) with integer attributes `line` and `col` giving where the problem is.

## `tokenize(source)`

Returns a list of `Token`. The list always ends with one `EOF` token whose `text` is `""` and whose position is the position just after the last character of the source.

### Skipped input

- Spaces, tabs, `\r` and `\n` separate tokens and produce none.
- A `#` starts a comment that runs to the end of the line. Comments produce no tokens.

### Token kinds

| Kind | Text | Rule |
| --- | --- | --- |
| `NUMBER` | the characters as written | see below |
| `IDENT` | the characters as written | a letter or `_`, then letters, digits or `_` |
| `STRING` | the decoded contents, without the quotes | see below |
| `OP` | the operator | one of `**` `==` `!=` `<=` `>=` `&&` `||` `+` `-` `*` `/` `%` `<` `>` `=` `!` |
| `LPAREN` | `(` | |
| `RPAREN` | `)` | |
| `COMMA` | `,` | |
| `EOF` | `""` | |

Operators use the longest match: `**` is one token, not two `*` tokens. A single `&` or `|` is not a token.

### Numbers

A number is one of:

- one or more digits, optionally followed by a fraction, optionally followed by an exponent
- a fraction on its own (such as `.5`), optionally followed by an exponent

A fraction is a `.` followed by one or more digits. An exponent is `e` or `E`, an optional `+` or `-`, and one or more digits.

Each optional part is consumed only if it is complete. If it is not, the number ends before it and tokenizing continues from there:

- `1.5.2` is `NUMBER 1.5` then `NUMBER .2`.
- `1e` is `NUMBER 1` then `IDENT e`.
- `2e+x` is `NUMBER 2`, `IDENT e`, `OP +`, `IDENT x`.
- In `1.`, the number is `1`, and the `.` that follows is an error because a `.` not followed by a digit is not a token.

### Strings

A string starts and ends with a double quote. Inside it, these escapes are decoded: `\"` to a double quote, `\\` to a backslash, `\n` to a newline and `\t` to a tab. The token's `text` is the decoded contents.

- Any other character after a backslash raises `TokenizeError` at the position of the backslash.
- A string that reaches a newline or the end of the source before its closing quote raises `TokenizeError` at the position of the opening quote.

### Errors

Any character that cannot start a token raises `TokenizeError` at that character's position.

## Requirements

- Put everything in one module. It will be saved as `solution.py` and imported by a pytest file you cannot see.
- Use only the Python standard library. The code runs on Python 3.12 with no network access.
- Use exactly the names and signatures above.
