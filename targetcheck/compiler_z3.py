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
        self.division_denominators: list[z3.ExprRef] = []

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
        if node.id in {"true", "false"}:
            return z3.BoolVal(node.id == "true")
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
            # Mathematical division is exact rational division. Z3 otherwise
            # interprets two integer literals as Euclidean division before a
            # surrounding Real equality can coerce the result.
            if z3.is_int(left):
                left = z3.ToReal(left)
            if z3.is_int(right):
                right = z3.ToReal(right)
            self.division_denominators.append(right)
            return left / right
        if isinstance(node.op, ast.Mod):
            self.division_denominators.append(right)
            return left % right
        if isinstance(node.op, ast.Pow):
            # Z3's generic power operator coerces even IntVal(18)**IntVal(6)
            # to a Real expression. Expand nonnegative literal integer powers
            # so integer modular arithmetic keeps its Int sort.
            if isinstance(node.right, ast.Constant) and isinstance(node.right.value, int):
                exponent = node.right.value
                if exponent >= 0:
                    result = z3.IntVal(1) if z3.is_int(left) else z3.RealVal(1)
                    factor = left
                    # Exponentiation by squaring preserves the Int sort without
                    # constructing a linear-size term for large literals.
                    while exponent:
                        if exponent & 1:
                            result = result * factor
                        exponent >>= 1
                        if exponent:
                            factor = factor * factor
                    return result
            # Let Z3 interpret powers, including exact rational exponents such
            # as 1/2 and 1/3. The division visitor keeps those exact.
            try:
                return left**right
            except (TypeError, z3.Z3Exception) as exc:
                raise UnsupportedExpression(f"invalid power: {exc}") from exc
        raise UnsupportedExpression(f"unsupported binary operator: {type(node.op).__name__}")

    def visit_Call(self, node: ast.Call) -> z3.ExprRef:
        if not isinstance(node.func, ast.Name) or node.keywords:
            raise UnsupportedExpression("unsupported function call")
        name = node.func.id
        if name in {"And", "Or"} and node.args:
            values = [self.visit(argument) for argument in node.args]
            return z3.And(*values) if name == "And" else z3.Or(*values)
        if name == "Xor" and len(node.args) >= 2:
            return z3.Xor(*(self.visit(argument) for argument in node.args))
        if name == "Distinct" and len(node.args) >= 2:
            return z3.Distinct(*(self.visit(argument) for argument in node.args))
        if name == "Sum" and node.args:
            values: list[z3.ExprRef] = []
            for argument in node.args:
                value = self.visit(argument)
                values.extend(value if isinstance(value, list) else [value])
            return z3.Sum(*values)
        if name == "Count" and node.args:
            values = [self.visit(argument) for argument in node.args]
            return z3.Sum(*(z3.If(value, 1, 0) for value in values))
        if name == "ExactlyOne" and node.args:
            values = [self.visit(argument) for argument in node.args]
            return z3.PbEq([(value, 1) for value in values], 1)
        if name in {"AtMost", "AtLeast", "Exactly"} and len(node.args) >= 2:
            bound_node, *value_nodes = node.args
            if not isinstance(bound_node, ast.Constant) or not isinstance(bound_node.value, int):
                raise UnsupportedExpression(f"{name} requires a literal integer bound")
            values = [self.visit(argument) for argument in value_nodes]
            bound = bound_node.value
            if name == "AtMost":
                return z3.PbLe([(value, 1) for value in values], bound)
            if name == "AtLeast":
                return z3.PbGe([(value, 1) for value in values], bound)
            return z3.PbEq([(value, 1) for value in values], bound)
        if name == "Not" and len(node.args) == 1:
            return z3.Not(self.visit(node.args[0]))
        if name == "Implies" and len(node.args) == 2:
            return z3.Implies(self.visit(node.args[0]), self.visit(node.args[1]))
        if name == "If" and len(node.args) == 3:
            return z3.If(*(self.visit(argument) for argument in node.args))
        if name in {"Mod", "mod"} and len(node.args) == 2:
            left, right = (self.visit(argument) for argument in node.args)
            self.division_denominators.append(right)
            return left % right
        if len(node.args) != 1:
            raise UnsupportedExpression("unsupported function call")
        value = self.visit(node.args[0])
        if name in {"ToReal", "to_real"}:
            return z3.ToReal(value) if z3.is_int(value) else value
        if name in {"ToInt", "to_int"}:
            return value if z3.is_int(value) else z3.ToInt(value)
        if name == "sqrt":
            return value ** z3.RealVal("1/2")
        if name == "cbrt":
            return value ** z3.RealVal("1/3")
        if name in {"ceil", "ceiling"}:
            return value if z3.is_int(value) else -z3.ToInt(-value)
        if name == "floor":
            return value if z3.is_int(value) else z3.ToInt(value)
        if name in {"abs", "Abs"}:
            return z3.Abs(value)
        raise UnsupportedExpression(f"unsupported function: {name}")

    def visit_List(self, node: ast.List) -> list[z3.ExprRef]:
        return [self.visit(element) for element in node.elts]

    def visit_Tuple(self, node: ast.Tuple) -> list[z3.ExprRef]:
        return [self.visit(element) for element in node.elts]

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
    domain_assertions: list[z3.BoolRef] = []
    for variable in spec.variables:
        symbol = symbols[variable.name]
        if variable.lower is not None:
            domain_assertions.append(symbol >= variable.lower)
        if variable.upper is not None:
            domain_assertions.append(symbol <= variable.upper)
        if variable.values is not None:
            domain_assertions.append(z3.Or(*(symbol == value for value in variable.values)))
    constraint_assertions: list[z3.BoolRef] = []
    for constraint in spec.constraints:
        compiled = compiler.compile(constraint.expression)
        if not z3.is_bool(compiled):
            raise UnsupportedExpression(f"constraint {constraint.id} is not Boolean")
        constraint_assertions.append(compiled)
    target = compiler.compile(spec.target)
    # Arithmetic division and modulo are defined only for nonzero divisors.
    # Put guards before the explicit constraints so callers that inspect the
    # final assertion still see the final user constraint.
    denominator_guards = [denominator != 0 for denominator in compiler.division_denominators]
    assertions = (*domain_assertions, *denominator_guards, *constraint_assertions)
    return CompiledSpec(symbols, assertions, target)


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
