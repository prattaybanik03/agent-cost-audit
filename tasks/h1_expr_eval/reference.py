"""Reference solution. Never shown to a model."""

import math
import re


class ExprError(Exception):
    pass


class ParseError(ExprError):
    def __init__(self, message, position):
        super().__init__(f"{message} at position {position}")
        self.position = position


class EvalError(ExprError):
    pass


_TOKEN = re.compile(
    r"""
    (?P<number>(?:[0-9]+\.[0-9]*|\.[0-9]+|[0-9]+)(?:[eE][+-]?[0-9]+)?)
  | (?P<name>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<op>\*\*|//|<=|>=|==|!=|[-+*/%<>(),?:])
    """,
    re.VERBOSE,
)
_COMPARISONS = ("<", "<=", ">", ">=", "==", "!=")


def _tokenize(text):
    tokens = []
    index = 0
    while index < len(text):
        if text[index].isspace():
            index += 1
            continue
        match = _TOKEN.match(text, index)
        if match is None:
            raise ParseError(f"unexpected character {text[index]!r}", index)
        tokens.append((match.lastgroup, match.group(), index))
        index = match.end()
    tokens.append(("end", "", len(text)))
    return tokens


class _Parser:
    def __init__(self, text):
        self.tokens = _tokenize(text)
        self.index = 0

    @property
    def current(self):
        return self.tokens[self.index]

    def at_op(self, *ops):
        kind, text, _ = self.current
        return kind == "op" and text in ops

    def advance(self):
        token = self.current
        self.index += 1
        return token

    def fail(self, message="unexpected token"):
        raise ParseError(message, self.current[2])

    def expect(self, op):
        if not self.at_op(op):
            self.fail(f"expected {op!r}")
        self.advance()

    def parse(self):
        node = self.conditional()
        if self.current[0] != "end":
            self.fail()
        return node

    def conditional(self):
        condition = self.comparison()
        if not self.at_op("?"):
            return condition
        self.advance()
        if_true = self.conditional()
        self.expect(":")
        if_false = self.conditional()
        return ("cond", condition, if_true, if_false)

    def comparison(self):
        left = self.additive()
        if not self.at_op(*_COMPARISONS):
            return left
        op = self.advance()[1]
        right = self.additive()
        if self.at_op(*_COMPARISONS):
            self.fail("comparisons cannot be chained")
        return ("binary", op, left, right)

    def additive(self):
        node = self.term()
        while self.at_op("+", "-"):
            op = self.advance()[1]
            node = ("binary", op, node, self.term())
        return node

    def term(self):
        node = self.unary()
        while self.at_op("*", "/", "//", "%"):
            op = self.advance()[1]
            node = ("binary", op, node, self.unary())
        return node

    def unary(self):
        if self.at_op("+", "-"):
            op = self.advance()[1]
            return ("unary", op, self.unary())
        return self.power()

    def power(self):
        base = self.primary()
        if self.at_op("**"):
            self.advance()
            return ("binary", "**", base, self.unary())
        return base

    def primary(self):
        kind, text, _ = self.current
        if kind == "number":
            self.advance()
            is_int = text.isdigit()
            return ("number", int(text) if is_int else float(text))
        if kind == "name":
            self.advance()
            if not self.at_op("("):
                return ("variable", text)
            self.advance()
            args = []
            if not self.at_op(")"):
                args.append(self.conditional())
                while self.at_op(","):
                    self.advance()
                    args.append(self.conditional())
            self.expect(")")
            return ("call", text, args)
        if self.at_op("("):
            self.advance()
            node = self.conditional()
            self.expect(")")
            return node
        self.fail()


def _binary(op, left, right):
    try:
        if op == "+":
            return left + right
        if op == "-":
            return left - right
        if op == "*":
            return left * right
        if op == "/":
            return left / right
        if op == "//":
            return left // right
        if op == "%":
            return left % right
        if op == "**":
            result = left**right
            if isinstance(result, complex):
                raise EvalError("result is not a real number")
            return result
    except ZeroDivisionError:
        raise EvalError("division by zero") from None
    except OverflowError:
        raise EvalError("result is too large") from None
    if op == "<":
        return int(left < right)
    if op == "<=":
        return int(left <= right)
    if op == ">":
        return int(left > right)
    if op == ">=":
        return int(left >= right)
    if op == "==":
        return int(left == right)
    return int(left != right)


def _call(name, args):
    count = len(args)
    if name == "abs" and count == 1:
        return abs(args[0])
    if name in ("min", "max") and count >= 1:
        return min(args) if name == "min" else max(args)
    if name == "sqrt" and count == 1:
        if args[0] < 0:
            raise EvalError("sqrt of a negative number")
        return math.sqrt(args[0])
    if name == "round" and count == 1:
        return round(args[0])
    if name == "round" and count == 2:
        if isinstance(args[1], bool) or not isinstance(args[1], int):
            raise EvalError("round: the number of places must be an int")
        return round(args[0], args[1])
    if name in ("abs", "min", "max", "sqrt", "round"):
        raise EvalError(f"wrong number of arguments for {name}")
    raise EvalError(f"unknown function {name!r}")


def _evaluate(node, variables):
    kind = node[0]
    if kind == "number":
        return node[1]
    if kind == "variable":
        if node[1] not in variables:
            raise EvalError(f"unknown variable {node[1]!r}")
        return variables[node[1]]
    if kind == "unary":
        value = _evaluate(node[2], variables)
        return -value if node[1] == "-" else +value
    if kind == "binary":
        left = _evaluate(node[2], variables)
        right = _evaluate(node[3], variables)
        return _binary(node[1], left, right)
    if kind == "cond":
        chosen = node[2] if _evaluate(node[1], variables) != 0 else node[3]
        return _evaluate(chosen, variables)
    return _call(node[1], [_evaluate(arg, variables) for arg in node[2]])


def evaluate(expression, variables=None):
    tree = _Parser(expression).parse()
    return _evaluate(tree, variables or {})
