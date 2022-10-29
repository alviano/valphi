from clingo import Number


class Context:
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
    def godel_implication(left, right, den):
        return den if left.number <= right.number else right
