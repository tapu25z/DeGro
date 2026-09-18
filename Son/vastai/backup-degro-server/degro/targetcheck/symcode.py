from __future__ import annotations

import ast
from typing import Any

import sympy


class UnsafeSymCode(ValueError):
    pass


_FUNCTIONS = {
    name: getattr(sympy, name)
    for name in (
        "Abs", "Eq", "Integer", "Max", "Min", "Mod", "Rational", "Symbol",
        "binomial", "ceiling", "cos", "diff", "expand", "factor", "factorial",
        "floor", "gcd", "integrate", "lcm", "log", "product", "simplify",
        "sin", "solve", "solveset", "sqrt", "summation", "symbols", "tan",
    )
}
_CONSTANTS = {"E": sympy.E, "oo": sympy.oo, "pi": sympy.pi}
_ALLOWED_NODES = (
    ast.Module, ast.Assign, ast.Expr, ast.Name, ast.Store, ast.Load, ast.Constant,
    ast.Tuple, ast.List, ast.Subscript, ast.Slice, ast.Call, ast.keyword,
    ast.BinOp, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.UnaryOp, ast.UAdd, ast.USub, ast.Compare, ast.Eq, ast.NotEq, ast.Lt,
    ast.LtE, ast.Gt, ast.GtE,
)


def execute_symcode(code: str) -> Any:
    """Execute a tiny assignment-only SymPy language and return ``result``."""
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as exc:
        raise UnsafeSymCode(str(exc)) from exc
    assigned: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise UnsafeSymCode(f"disallowed syntax: {type(node).__name__}")
        if isinstance(node, ast.Attribute):
            raise UnsafeSymCode("attribute access is disallowed")
        if isinstance(node, ast.Call) and not isinstance(node.func, ast.Name):
            raise UnsafeSymCode("only direct calls to approved SymPy functions are allowed")
        if isinstance(node, ast.Call) and node.func.id not in _FUNCTIONS:
            raise UnsafeSymCode(f"function is not approved: {node.func.id}")
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            raise UnsafeSymCode("dunder names are disallowed")
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            assigned.add(node.id)
    allowed_names = set(_FUNCTIONS) | set(_CONSTANTS) | assigned
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id not in allowed_names:
            raise UnsafeSymCode(f"unknown name: {node.id}")
    if "result" not in assigned:
        raise UnsafeSymCode("code must assign the scalar answer to result")
    scope = {"__builtins__": {}, **_FUNCTIONS, **_CONSTANTS}
    exec(compile(tree, "<symcode>", "exec"), scope, scope)
    result = scope["result"]
    if isinstance(result, (list, tuple)):
        if len(result) != 1:
            raise UnsafeSymCode("result must be a single scalar")
        result = result[0]
    if not getattr(result, "is_number", isinstance(result, (int, float))):
        raise UnsafeSymCode("result is not numeric")
    return result
