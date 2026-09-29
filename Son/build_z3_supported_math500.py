#!/usr/bin/env python3
"""Build the strict MATH-500 cohort used by the direct DeGro/Z3 flow.

The filter is intentionally independent of model outputs and previous run
results.  It keeps scalar problems that can be expressed in the arithmetic
fragment accepted by ``targetcheck/compiler_z3.py`` and records one explicit
reason for every excluded row.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from run_degro_direct import scalar_approx


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/math500/test.jsonl"
OUTPUT = ROOT / "Son/math500_scalar_degro.jsonl"
EXCLUSIONS = ROOT / "Son/math500_scalar_degro_exclusions.jsonl"


# Problems whose requested result needs a construct that the current
# Int/Real/Bool scalar ModelSpec does not expose: optimization, cardinality or
# aggregation over a solution set, limits, recursive/infinite structures,
# native complex arithmetic, or primality predicates.
UNSUPPORTED_MODELSPEC_IDS = {
    "test/algebra/2427.json",
    "test/algebra/661.json",
    "test/algebra/2176.json",
    "test/algebra/1425.json",
    "test/prealgebra/1686.json",
    "test/prealgebra/1128.json",
    "test/prealgebra/805.json",
    "test/intermediate_algebra/232.json",
    "test/intermediate_algebra/2022.json",
    "test/intermediate_algebra/1544.json",
    "test/intermediate_algebra/1930.json",
    "test/intermediate_algebra/515.json",
    "test/intermediate_algebra/1462.json",
    "test/intermediate_algebra/776.json",
    "test/intermediate_algebra/1168.json",
    "test/intermediate_algebra/1232.json",
    "test/number_theory/631.json",
    "test/number_theory/149.json",
    "test/number_theory/183.json",
    "test/number_theory/255.json",
    "test/number_theory/22.json",
    # Order statistics, cardinality over an implicit set, and aggregation over
    # all roots require collection semantics that the scalar ModelSpec does
    # not expose.
    "test/prealgebra/1804.json",       # median of a table/multiset
    "test/prealgebra/1139.json",       # number of distinct parenthesized values
    "test/number_theory/928.json",     # cardinality of a digit-set intersection
    # These need complex numbers or nonlinear/transcendental fragments that
    # are not reliable in the current direct Z3 flow.
    "test/intermediate_algebra/1410.json",
    "test/intermediate_algebra/362.json",
    "test/intermediate_algebra/894.json",
    "test/algebra/2430.json",
}


RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "diagram_or_image_required",
        re.compile(r"\[asy\]|\[/asy\]|\b(?:diagram|pictured)\b|\b(?:as\s+)?shown\b|\bin\s+the\s+figure\b", re.I),
    ),
    (
        "transcendental_trigonometry",
        re.compile(r"\\(?:sin|cos|tan|sec|csc|cot|arcsin|arccos|arctan)\b|\b(?:sine|cosine|trigonometric)\b", re.I),
    ),
    (
        "transcendental_logarithm",
        re.compile(r"\\(?:log|ln)\b|\blogarithms?\b|\blogarithmic\b|\blog\s*[_^]?\s*\d", re.I),
    ),
    (
        "transcendental_variable_exponent",
        re.compile(r"(?:\d|e)\s*\^\s*(?:\{[^}]*[A-Za-z][^}]*\}|[A-Za-z])|\bexponential\b", re.I),
    ),
    (
        "transcendental_pi",
        re.compile(r"\\pi\b|\bpi\b|3\.14159", re.I),
    ),
    (
        "symbolic_calculus",
        re.compile(r"\b(?:derivative|differentiat\w*|integral|integrat\w*|antiderivative)\b", re.I),
    ),
    (
        "complex_vector_or_matrix_theory",
        re.compile(
            r"\bcomplex\b|\\omega\b|\\overline\s*\{|\\begin\{pmatrix\}|"
            r"\\mathbf\s*\{|\\bold\s*\{|\bvectors?\b|\bdot product\b|\bprojection\b",
            re.I,
        ),
    ),
    (
        "higher_order_polynomial_or_custom_function",
        re.compile(
            r"\bpolynomial\b|\boperation\s+[@#*]|\boperation\s+.+\bis defined\b|"
            r"\bfunctional equation\b",
            re.I,
        ),
    ),
    (
        "implicit_set_cardinality",
        re.compile(
            r"\bhow many\s+(?:positive\s+|negative\s+)?(?:two-digit\s+)?integers?\b[\s\S]{0,100}"
            r"(?:factors?\s+of|divisible\s+by|solution\s+set)|"
            r"\bhow many\s+of\s+the\s+first\b[\s\S]{0,100}\bdivisible\s+by\b|"
            r"\bhow many\s+integer\s+coordinates?\b|"
            r"\bhow many\s+[xy]-intercepts?\b",
            re.I,
        ),
    ),
    (
        "combinatorial_count_or_probability",
        re.compile(
            r"\bprobability\b|\bhow many ways\b|\bnumber of ways\b|\barrangements?\b|"
            r"\bpermutations?\b|\bcombinations?\b|\bchoose\b|\bdice\b|\bdie is\b|"
            r"\bcards?\b|\bcommittee\b|\brandom(?:ly)?\b|\boutcomes?\b",
            re.I,
        ),
    ),
    (
        "set_or_population_aggregation",
        re.compile(r"\b(?:both|all three)\s+(?:clubs|classes|subjects)\b|\bdon't take any\b|\bVenn\b", re.I),
    ),
    (
        "optimization_or_order_search",
        re.compile(
            r"\b(?:maximum|minimum|maximize|minimize|largest|smallest)\b|"
            r"(?<!\bat )\bleast\s+(?:positive|negative|possible|integer|number|multiple|value)\b|"
            r"\bgreatest\b",
            re.I,
        ),
    ),
    (
        "aggregate_or_enumeration_over_solution_set",
        re.compile(
            r"\b(?:sum|product)\s+of\s+(?:all\s+)?(?:the\s+)?(?:roots|solutions|values)\b|"
            r"\bhow many\s+(?:integer|integral|real|positive|negative)\s+(?:solutions|values|roots|numbers)\b|"
            r"\bin total,?\s+how many values can be obtained\b|"
            r"\bnumber\s+of\s+(?:integer|integral|real|positive|negative)?\s*(?:solutions|roots)\b|"
            r"\bfind\s+all\b|\ball\s+(?:integer|real)\s+(?:solutions|values)\b",
            re.I,
        ),
    ),
    (
        "unsupported_number_theory_operator",
        re.compile(
            r"\bgreatest common (?:factor|divisor)\b|\bleast common multiple\b|\b(?:gcd|lcm)\b|"
            r"\bprime(?:s| factorization| factor)?\b|\bdivisors?\b|\bfactorial\b|!\s*(?:[=+\-*/]|$)",
            re.I,
        ),
    ),
    (
        "recursive_sequence_or_function",
        re.compile(
            r"\bfibonacci\b|\bdefined recursively\b|\brecurrence\b|"
            r"[xa]_\{?n\}?\s*&?=|[xa]_\{?i\s*\+\s*1\}?\s*&?=|\bsubsequent terms are produced\b",
            re.I,
        ),
    ),
    (
        "quantified_or_recursive_relation",
        re.compile(r"\bfor all (?:real|integer|positive|negative|two-dimensional)\b|\bfor every positive integer\b", re.I),
    ),
    (
        "unsupported_factorial_or_power_operator",
        re.compile(r"\bsuperfactorial\b|(?:\b\d+|\bn)\s*!|\bwhat power of\b", re.I),
    ),
    (
        "geometry_requiring_transcendental_constant",
        re.compile(
            r"\b(?:sphere|circular|cylinder|cone)\b.*\b(?:volume|surface area|circumference|radius)\b|"
            r"\b(?:volume|surface area|circumference)\b.*\b(?:sphere|circular|cylinder|cone)\b",
            re.I,
        ),
    ),
    (
        "advanced_geometric_construction",
        re.compile(
            r"\b(?:centroid|tetrahedron|equiangular|orthocenter)\b|"
            r"\bfoot of the altitude\b|\bplane parallel to\b|"
            r"\bmedians?\b.*\bintersect\b",
            re.I,
        ),
    ),
    (
        "non_scalar_question",
        re.compile(
            r"\bwhat real values\b|\bfind (?:all|the) values\b|\bvalues of [A-Za-z]\b.*\bnot in the domain\b|"
            r"\bnot in the domain of\b",
            re.I,
        ),
    ),
    (
        "implicit_vector_geometry",
        re.compile(
            r"\bset of points\b[\s\S]{0,150}\bangle between\b|"
            r"\bangle between\b[\s\S]{0,60}\blines\b|"
            r"(?:\([+-]?\d+\s*,\s*[+-]?\d+\s*,\s*[+-]?\d+\).*){2,}.*\\angle",
            re.I,
        ),
    ),
)


def answer_exclusion(answer: str) -> str | None:
    raw = answer.strip()
    if re.search(r"\\pm|\+\s*or\s*-|\bor\b", raw, re.I):
        return "multiple_target_values"
    if re.search(r"\\infty|\\cup|\\le|\\ge|<|>", raw):
        return "interval_or_set_answer"
    if re.search(r"\\pi\b", raw):
        return "transcendental_pi_answer"
    if re.search(r"(?<![A-Za-z])i(?![A-Za-z])", raw):
        return "complex_answer"
    if re.search(r"\d_\{?\d+\}?", raw):
        return "non_decimal_numeric_notation"
    # Parenthesized/bracketed answers in MATH-500 are coordinates, tuples,
    # intervals, or matrices. Scalar grouping is written with braces instead.
    if any(mark in raw for mark in (r"\left(", r"\right)", r"\left[", r"\right]", "[", "]")):
        return "non_scalar_answer"
    # A comma followed by LaTeX negative spacing is a thousands separator.
    without_thousands = re.sub(r",\s*\\!\s*", "", raw)
    if re.search(r"\d\s*,\s*[+-]?\d", without_thousands):
        return "multiple_target_values"
    if scalar_approx(raw) is None:
        return "non_numeric_or_unscorable_answer"
    return None


def exclusion_reason(row: dict[str, object]) -> str | None:
    if str(row["unique_id"]) in UNSUPPORTED_MODELSPEC_IDS:
        return "unsupported_by_current_modelspec"
    answer_reason = answer_exclusion(str(row["answer"]))
    if answer_reason is not None:
        return answer_reason
    problem = str(row["problem"])
    if str(row.get("subject")) == "Counting & Probability":
        return "combinatorial_count_or_probability"
    for reason, pattern in RULES:
        if pattern.search(problem):
            return reason
    # Radical constants are algebraic and are kept. Equations with a variable
    # under a radical, nested radicals, and ceil/floor of a radical routinely
    # leave Z3's complete polynomial-real fragment.
    if re.search(r"\\sqrt\s*(?:\[[^]]+\])?\s*(?:\{[^}]*[A-Za-z]|[A-Za-z])", problem) or problem.count(r"\sqrt") > 1:
        return "non_polynomial_radical_constraint"
    if re.search(r"\\(?:lceil|lfloor)[\s\S]{0,40}\\sqrt", problem):
        return "non_polynomial_radical_constraint"
    # Keep ordinary polynomial powers, but reject very high symbolic powers;
    # these caused solver UNKNOWN rather than exercising DeGro repair.
    for exponent in re.findall(r"\^\s*\{?(\d+)\}?", problem):
        if int(exponent) > 12 and re.search(r"[A-Za-z)]\s*\^", problem):
            return "high_degree_symbolic_arithmetic"
    if re.search(r"\\pmod|\bmodulo\b|\bremainder\b", problem, re.I):
        if re.search(r"\([^)]*[A-Za-z][^)]*\)\s*\([^)]*[A-Za-z]", problem) or re.search(r"[A-Za-z]\s*\^", problem):
            return "nonlinear_integer_modular_arithmetic"
    if len(set(re.findall(r"[xyz]_\{?\d+\}?", problem))) >= 4:
        return "large_multivariate_nonlinear_system"
    if all(re.search(rf"\b{name}\b", problem) for name in ("x", "y", "z")) and re.search(r"\^\s*3|xyz", problem):
        return "large_multivariate_nonlinear_system"
    return None


def main() -> None:
    rows = [json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines() if line.strip()]
    selected: list[dict[str, object]] = []
    excluded: list[dict[str, object]] = []
    for index, row in enumerate(rows):
        reason = exclusion_reason(row)
        if reason is None:
            selected.append(row)
        else:
            excluded.append({"original_index": index, "unique_id": row["unique_id"], "reason": reason})

    OUTPUT.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in selected), encoding="utf-8")
    EXCLUSIONS.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in excluded), encoding="utf-8")

    reasons = Counter(row["reason"] for row in excluded)
    print(f"source={len(rows)} selected={len(selected)} excluded={len(excluded)}")
    for reason, count in sorted(reasons.items()):
        print(f"{reason}: {count}")


if __name__ == "__main__":
    main()
