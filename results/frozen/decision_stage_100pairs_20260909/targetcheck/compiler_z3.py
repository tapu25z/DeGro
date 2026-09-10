from __future__ import annotations

import ast
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

import z3

from .expressions import ExpressionNormalizationError, normalize_expression
from .modelspec import ModelSpec


class UnsupportedExpression(ValueError):
    pass


_COMPARE = {
    ast.Eq: lambda a, b: a == b,
    ast.NotEq: lambda a, b: a != b,
    ast.Lt: lambda a, b: a < b,
    ast.LtE: lambda a, b: a <= b,
    ast.Gt: lambda a, b: a > b,
    ast.GtE: lambda a, b: a >= b,
}


class ExpressionCompiler(ast.NodeVisitor):
    """Compile a deliberately small, auditable arithmetic fragment to Z3."""

    def __init__(self, symbols: dict[str, z3.ExprRef]):
        self.symbols = symbols

    def compile(self, expression: str) -> z3.ExprRef:
        try:
            normalized = normalize_expression(expression, self.symbols)
            node = ast.parse(normalized, mode="eval").body
        except (ExpressionNormalizationError, SyntaxError) as exc:
            raise UnsupportedExpression(str(exc)) from exc
        return self.visit(node)

    def generic_visit(self, node: ast.AST) -> Any:
        raise UnsupportedExpression(f"unsupported syntax: {type(node).__name__}")

    def visit_Name(self, node: ast.Name) -> z3.ExprRef:
        if node.id not in self.symbols:
            raise UnsupportedExpression(f"unknown variable: {node.id}")
        return self.symbols[node.id]

    def visit_Constant(self, node: ast.Constant) -> Any:
        if isinstance(node.value, bool):
            return z3.BoolVal(node.value)
        if isinstance(node.value, int):
            return z3.IntVal(node.value)
        if isinstance(node.value, float):
            return z3.RealVal(str(node.value))
        raise UnsupportedExpression(f"unsupported constant: {node.value!r}")

    def visit_UnaryOp(self, node: ast.UnaryOp) -> z3.ExprRef:
        value = self.visit(node.operand)
        if isinstance(node.op, ast.USub):
            return -value
        if isinstance(node.op, ast.UAdd):
            return value
        if isinstance(node.op, ast.Not):
            return z3.Not(value)
        raise UnsupportedExpression(f"unsupported unary operator: {type(node.op).__name__}")

    def visit_BinOp(self, node: ast.BinOp) -> z3.ExprRef:
        left, right = self.visit(node.left), self.visit(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.Mod):
            return left % right
        if isinstance(node.op, ast.Pow) and isinstance(node.right, ast.Constant):
            if isinstance(node.right.value, int) and 0 <= node.right.value <= 4:
                return left**node.right.value
        raise UnsupportedExpression(f"unsupported binary operator: {type(node.op).__name__}")

    def visit_Compare(self, node: ast.Compare) -> z3.ExprRef:
        if len(node.ops) != len(node.comparators):
            raise UnsupportedExpression("malformed comparison")
        terms = []
        left = self.visit(node.left)
        for op, comparator in zip(node.ops, node.comparators, strict=True):
            right = self.visit(comparator)
            fn = _COMPARE.get(type(op))
            if fn is None:
                raise UnsupportedExpression(f"unsupported comparison: {type(op).__name__}")
            terms.append(fn(left, right))
            left = right
        return z3.And(*terms)

    def visit_BoolOp(self, node: ast.BoolOp) -> z3.ExprRef:
        values = [self.visit(value) for value in node.values]
        if isinstance(node.op, ast.And):
            return z3.And(*values)
        if isinstance(node.op, ast.Or):
            return z3.Or(*values)
        raise UnsupportedExpression(f"unsupported Boolean operator: {type(node.op).__name__}")


@dataclass(frozen=True)
class CompiledSpec:
    symbols: dict[str, z3.ExprRef]
    assertions: tuple[z3.BoolRef, ...]
    target: z3.ExprRef


def compile_spec(spec: ModelSpec, suffix: str = "") -> CompiledSpec:
    symbols: dict[str, z3.ExprRef] = {}
    for variable in spec.variables:
        solver_name = f"{variable.name}{suffix}"
        if variable.sort == "Int":
            symbols[variable.name] = z3.Int(solver_name)
        elif variable.sort == "Real":
            symbols[variable.name] = z3.Real(solver_name)
        elif variable.sort == "Bool":
            symbols[variable.name] = z3.Bool(solver_name)
        else:
            raise UnsupportedExpression(f"unsupported sort: {variable.sort}")

    compiler = ExpressionCompiler(symbols)
    assertions: list[z3.BoolRef] = []
    for variable in spec.variables:
        symbol = symbols[variable.name]
        if variable.lower is not None:
            assertions.append(symbol >= variable.lower)
        if variable.upper is not None:
            assertions.append(symbol <= variable.upper)
        if variable.values is not None:
            assertions.append(z3.Or(*(symbol == value for value in variable.values)))
    for constraint in spec.constraints:
        compiled = compiler.compile(constraint.expression)
        if not z3.is_bool(compiled):
            raise UnsupportedExpression(f"constraint {constraint.id} is not Boolean")
        assertions.append(compiled)
    return CompiledSpec(symbols, tuple(assertions), compiler.compile(spec.target))


def model_value(model: z3.ModelRef, expression: z3.ExprRef) -> bool | int | str:
    value = model.eval(expression, model_completion=True)
    if z3.is_true(value):
        return True
    if z3.is_false(value):
        return False
    if z3.is_int_value(value):
        return value.as_long()
    if z3.is_rational_value(value):
        fraction = Fraction(value.numerator_as_long(), value.denominator_as_long())
        return str(fraction) if fraction.denominator != 1 else fraction.numerator
    return str(value)
