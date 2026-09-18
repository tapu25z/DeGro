from targetcheck.symcode_full import SymCodeExecutionError, execute_symcode_full, extract_python_code
from scripts.run_olympiadbench_symcode import is_correct


def test_extract_and_execute_full_symcode() -> None:
    text = "```python\nimport sympy as sp\nx = sp.Rational(1, 2)\nprint(r'\\boxed{{{}}}'.format(sp.latex(x)))\n```"
    assert execute_symcode_full(extract_python_code(text)) == r"\boxed{\frac{1}{2}}"


def test_reject_non_sympy_import() -> None:
    try:
        execute_symcode_full("import os\nprint(1)")
    except SymCodeExecutionError as exc:
        assert "only SymPy imports" in str(exc)
    else:
        raise AssertionError("unsafe import was accepted")


def test_multiple_answer_equivalence() -> None:
    assert is_correct(r"\boxed{m=\pm1\text{ or }m=\pm7}", ["1,-1,7,-7"])


def test_symbolic_answer_does_not_collapse_to_constant() -> None:
    assert not is_correct("2", ["2k+2"])
    assert is_correct("2k+2", ["2k+2"])
