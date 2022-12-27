import clingo
from clingo import Number

from valphi.utils import validate


class Context:
    @staticmethod
    def is_named_concept(term):
        if term.type == clingo.SymbolType.Function and term.name not in ["top", "bot", "and", "or", "neg", "impl"]:
            return Number(1)
        return Number(0)

    @staticmethod
    def str_to_int(s):
        if s.type == clingo.SymbolType.Number:
            return s
        f = float(s.string)
        validate("is int", f.is_integer(), equals=True)
        return Number(int(f))

    @staticmethod
    def min(a, b):
        return a if a < b else b

    @staticmethod
    def max(a, b):
        return a if a > b else b

    @staticmethod
    def lt(num, den, real):
        return Number(1) if num.number < float(real.string) * den.number else Number(0)

    @staticmethod
    def gt(num, den, real):
        return Number(1) if num.number > float(real.string) * den.number else Number(0)

    @staticmethod
    def implication(left, right, den):
        return den if left.number <= right.number else right
