"""Reference solution. Never shown to a model."""

import re

_CELL = re.compile(r"[A-Z][1-9][0-9]{0,2}")
_INT = re.compile(r"[+-]?[0-9]+")
_FLOAT = re.compile(r"[+-]?([0-9]+\.?[0-9]*|\.[0-9]+)([eE][+-]?[0-9]+)?")
_TOKEN = re.compile(
    r"(?P<number>[0-9]+(?:\.[0-9]+)?)|(?P<cell>[A-Za-z]+[0-9]+)|(?P<word>[A-Za-z]+)|(?P<op>[-+*/(),:])"
)
_FUNCTIONS = ("SUM", "MIN", "MAX", "AVG", "COUNT")


class _Failure(Exception):
    """Carries an error string up through evaluation."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


class _SyntaxProblem(Exception):
    pass


def _check_name(cell):
    if not isinstance(cell, str) or not _CELL.fullmatch(cell):
        raise ValueError(f"invalid cell name: {cell!r}")


def _sort_key(cell):
    return cell[0], int(cell[1:])


def _tokenize(text):
    tokens = []
    index = 0
    while index < len(text):
        if text[index].isspace():
            index += 1
            continue
        match = _TOKEN.match(text, index)
        if match is None:
            raise _SyntaxProblem
        tokens.append((match.lastgroup, match.group()))
        index = match.end()
    tokens.append(("end", ""))
    return tokens


class _Parser:
    def __init__(self, text):
        self.tokens = _tokenize(text)
        self.index = 0

    def peek(self, offset=0):
        return self.tokens[min(self.index + offset, len(self.tokens) - 1)]

    def at(self, op, offset=0):
        return self.peek(offset) == ("op", op)

    def take(self):
        token = self.tokens[self.index]
        self.index += 1
        return token

    def expect(self, op):
        if not self.at(op):
            raise _SyntaxProblem
        self.index += 1

    def parse(self):
        node = self.expression()
        if self.peek()[0] != "end":
            raise _SyntaxProblem
        return node

    def expression(self):
        node = self.term()
        while self.at("+") or self.at("-"):
            op = self.take()[1]
            node = ("binary", op, node, self.term())
        return node

    def term(self):
        node = self.factor()
        while self.at("*") or self.at("/"):
            op = self.take()[1]
            node = ("binary", op, node, self.factor())
        return node

    def factor(self):
        if self.at("-") or self.at("+"):
            op = self.take()[1]
            return ("unary", op, self.factor())
        return self.primary()

    def primary(self):
        kind, text = self.peek()
        if kind == "number":
            self.take()
            return ("number", float(text) if "." in text else int(text))
        if kind == "cell":
            self.take()
            return ("ref", text.upper())
        if kind == "word":
            self.take()
            if not self.at("("):
                return ("word", text.upper())
            self.take()
            args = [self.argument()]
            while self.at(","):
                self.take()
                args.append(self.argument())
            self.expect(")")
            return ("call", text.upper(), args)
        if self.at("("):
            self.take()
            node = self.expression()
            self.expect(")")
            return node
        raise _SyntaxProblem

    def argument(self):
        if self.peek()[0] == "cell":
            first = self.peek()[1].upper()
            if self.at(":", 1):
                self.index += 2
                kind, text = self.take()
                if kind != "cell":
                    raise _SyntaxProblem
                return ("range", first, text.upper())
            if self.at(",", 1) or self.at(")", 1):
                self.index += 1
                return ("range", first, first)
        return self.expression()


def _range_cells(first, last):
    """Cells of a range, row by row. Returns None if a corner is not a valid cell name."""
    if not _CELL.fullmatch(first) or not _CELL.fullmatch(last):
        return None
    columns = sorted((first[0], last[0]))
    rows = sorted((int(first[1:]), int(last[1:])))
    return [
        f"{chr(column)}{row}"
        for row in range(rows[0], rows[1] + 1)
        for column in range(ord(columns[0]), ord(columns[1]) + 1)
    ]


def _references(node, found):
    kind = node[0]
    if kind == "ref":
        if _CELL.fullmatch(node[1]):
            found.add(node[1])
    elif kind == "range":
        found.update(_range_cells(node[1], node[2]) or ())
    elif kind == "unary":
        _references(node[2], found)
    elif kind == "binary":
        _references(node[2], found)
        _references(node[3], found)
    elif kind == "call":
        for arg in node[2]:
            _references(arg, found)
    return found


def _as_number(value):
    if value is None:
        return 0
    if isinstance(value, str):
        raise _Failure("#VALUE!")
    return value


class Sheet:
    def __init__(self):
        self._values = {}  # cell -> number or text
        self._formulas = {}  # cell -> parsed tree, or None for a syntax error
        self._references = {}  # cell -> set of cells its formula references

    def set(self, cell, raw):
        _check_name(cell)
        self._values.pop(cell, None)
        self._formulas.pop(cell, None)
        self._references.pop(cell, None)
        if isinstance(raw, int | float):
            self._values[cell] = raw
        elif raw == "":
            return
        elif raw.startswith("="):
            try:
                tree = _Parser(raw[1:]).parse()
            except _SyntaxProblem:
                tree = None
            self._formulas[cell] = tree
            self._references[cell] = _references(tree, set()) if tree else set()
        elif _INT.fullmatch(raw):
            self._values[cell] = int(raw)
        elif _FLOAT.fullmatch(raw):
            self._values[cell] = float(raw)
        else:
            self._values[cell] = raw

    def get(self, cell):
        _check_name(cell)
        if cell in self._values:
            return self._values[cell]
        if cell not in self._formulas:
            return ""
        try:
            return self._formula_value(cell, {})
        except _Failure as failure:
            return failure.code

    def dependents(self, cell):
        _check_name(cell)
        found = set()
        frontier = [cell]
        while frontier:
            current = frontier.pop()
            for other, references in self._references.items():
                if current in references and other not in found:
                    found.add(other)
                    frontier.append(other)
        found.discard(cell)
        return sorted(found, key=_sort_key)

    def _reaches_cycle(self, start):
        visiting = set()
        done = set()

        def visit(cell):
            if cell in done:
                return False
            if cell in visiting:
                return True
            visiting.add(cell)
            for reference in self._references.get(cell, ()):
                if visit(reference):
                    return True
            visiting.discard(cell)
            done.add(cell)
            return False

        return visit(start)

    def _formula_value(self, cell, memo):
        tree = self._formulas[cell]
        if tree is None:
            raise _Failure("#ERROR!")
        if self._reaches_cycle(cell):
            raise _Failure("#CYCLE!")
        return self._cell_value(cell, memo)

    def _cell_value(self, cell, memo):
        """A number, text, or None for an empty cell. Raises _Failure for an error value."""
        if cell in self._values:
            return self._values[cell]
        if cell not in self._formulas:
            return None
        if cell not in memo:
            tree = self._formulas[cell]
            try:
                if tree is None:
                    raise _Failure("#ERROR!")
                result = self._evaluate(tree, memo)
                memo[cell] = 0 if result is None else result
            except _Failure as failure:
                memo[cell] = failure
        if isinstance(memo[cell], _Failure):
            raise memo[cell]
        return memo[cell]

    def _evaluate(self, node, memo):
        kind = node[0]
        if kind == "number":
            return node[1]
        if kind == "ref":
            if not _CELL.fullmatch(node[1]):
                raise _Failure("#REF!")
            return self._cell_value(node[1], memo)
        if kind == "word":
            raise _Failure("#NAME?")
        if kind == "unary":
            value = _as_number(self._evaluate(node[2], memo))
            return -value if node[1] == "-" else value
        if kind == "binary":
            left = _as_number(self._evaluate(node[2], memo))
            right = _as_number(self._evaluate(node[3], memo))
            if node[1] == "+":
                return left + right
            if node[1] == "-":
                return left - right
            if node[1] == "*":
                return left * right
            if right == 0:
                raise _Failure("#DIV/0!")
            return left / right
        if kind == "range":
            raise _Failure("#ERROR!")  # unreachable: ranges only appear as call arguments
        return self._call(node[1], node[2], memo)

    def _call(self, name, args, memo):
        if name not in _FUNCTIONS:
            raise _Failure("#NAME?")
        numbers = []
        for arg in args:
            if arg[0] == "range":
                cells = _range_cells(arg[1], arg[2])
                if cells is None:
                    raise _Failure("#REF!")
                for cell in cells:
                    value = self._cell_value(cell, memo)
                    if value is not None and not isinstance(value, str):
                        numbers.append(value)
            else:
                numbers.append(_as_number(self._evaluate(arg, memo)))
        if name == "SUM":
            return sum(numbers)
        if name == "COUNT":
            return len(numbers)
        if name == "AVG":
            if not numbers:
                raise _Failure("#DIV/0!")
            return sum(numbers) / len(numbers)
        if not numbers:
            return 0
        return min(numbers) if name == "MIN" else max(numbers)
