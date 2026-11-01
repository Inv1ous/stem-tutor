"""Bounded verification for a small, explicitly supported class of identities.

Not a general mathematical proof checker. Unsupported expressions return None.
"""
from __future__ import annotations

import ast
import operator


def check_equality(left: str, right: str) -> bool | None:
    """Check a polynomial identity over real symbols, or exact rational arithmetic.

    False means the identity is not generally true, not that it fails for every
    possible value. Dividing by variables and functions are deliberately unsupported.
    """
    if not all(isinstance(s, str) and len(s) <= 128 for s in (left, right)):
        return None
    try:
        import sympy as sp
        trees = [ast.parse(s, mode="eval") for s in (left, right)]
        if sum(len(list(ast.walk(tree))) for tree in trees) > 80:
            return None
        names = {n.id for tree in trees for n in ast.walk(tree) if isinstance(n, ast.Name)}
        if len(names) > 3 or any(not n.isalpha() or len(n) > 12 for n in names):
            return None
        def bound(node):
            if isinstance(node, ast.Expression):
                return bound(node.body)
            if isinstance(node, ast.Constant) and type(node.value) is int and abs(node.value) <= 10000:
                return 0, max(1, abs(node.value).bit_length())
            if isinstance(node, ast.Name):
                return 1, 1
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
                return bound(node.operand)
            if isinstance(node, ast.BinOp):
                da, ba = bound(node.left)
                db, bb = bound(node.right)
                if isinstance(node.op, ast.Pow):
                    exponent = node.right
                    if not isinstance(exponent, ast.Constant) or type(exponent.value) is not int or not 0 <= exponent.value <= 8:
                        raise ValueError("unsupported exponent")
                    return da * exponent.value, ba * exponent.value
                if isinstance(node.op, (ast.Add, ast.Sub)):
                    return max(da, db), max(ba, bb) + 1
                if isinstance(node.op, (ast.Mult, ast.Div)):
                    return da + db, ba + bb
            raise ValueError("unsupported expression")
        if any(degree > 12 or bits > 512 for degree, bits in map(bound, trees)):
            return None
        symbols = {name: sp.Symbol(name, real=True) for name in names}
        def read(node):
            if isinstance(node, ast.Expression):
                return read(node.body)
            if isinstance(node, ast.Constant) and type(node.value) is int and abs(node.value) <= 10000:
                return sp.Integer(node.value)
            if isinstance(node, ast.Name):
                return symbols[node.id]
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
                value = read(node.operand)
                return value if isinstance(node.op, ast.UAdd) else -value
            if isinstance(node, ast.BinOp):
                a, b = read(node.left), read(node.right)
                if isinstance(node.op, ast.Pow):
                    if not b.is_Integer or b < 0 or b > 8:
                        raise ValueError("unsupported exponent")
                    return a ** b
                if isinstance(node.op, ast.Div):
                    if b.free_symbols or b == 0:
                        raise ValueError("unsupported denominator")
                    return a / b
                ops = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul}
                if type(node.op) in ops:
                    return ops[type(node.op)](a, b)
            raise ValueError("unsupported expression")
        lhs, rhs = (read(tree) for tree in trees)
        return bool(sp.Poly(lhs - rhs, *symbols.values()).is_zero) if symbols else bool(lhs == rhs)
    except (SyntaxError, ValueError, TypeError, ArithmeticError, ImportError):
        return None
