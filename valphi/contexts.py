import clingo
from clingo import Number

from dumbo_utils.validation import validate


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
    def eq(num, den, real):
        return Number(1) if num.number == float(real.string) * den.number else Number(0)

    @staticmethod
    def ne(num, den, real):
        return Number(1) if num.number != float(real.string) * den.number else Number(0)

    @staticmethod
    def lt(num, den, real):
        return Number(1) if num.number < float(real.string) * den.number else Number(0)

    @staticmethod
    def le(num, den, real):
        return Number(1) if num.number <= float(real.string) * den.number else Number(0)

    @staticmethod
    def ge(num, den, real):
        return Number(1) if num.number >= float(real.string) * den.number else Number(0)

    @staticmethod
    def gt(num, den, real):
        return Number(1) if num.number > float(real.string) * den.number else Number(0)

    @staticmethod
    def apply_operator(num, den, operator, real):
        validate("operator", operator.string, is_in=[">=", ">", "<=", "<", "=", "!="])
        if operator.string == ">=":
            return Context.ge(num, den, real)
        if operator.string == ">":
            return Context.gt(num, den, real)
        if operator.string == "<=":
            return Context.le(num, den, real)
        if operator.string == "<":
            return Context.lt(num, den, real)
        if operator.string == "=":
            return Context.eq(num, den, real)
        if operator.string == "!=":
            return Context.ne(num, den, real)

    @staticmethod
    def implication(left, right, den):
        return den if left.number <= right.number else right
