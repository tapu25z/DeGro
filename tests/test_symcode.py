import pytest

from targetcheck.symcode import UnsafeSymCode, execute_symcode


def test_execute_symcode_solves_equation():
    assert execute_symcode("x = symbols('x')\nresult = solve(Eq(x/2 + x/3, 5), x)[0]") == 6


def test_execute_symcode_rejects_imports():
    with pytest.raises(UnsafeSymCode):
        execute_symcode("import os\nresult = 1")


def test_execute_symcode_rejects_attribute_access():
    with pytest.raises(UnsafeSymCode):
        execute_symcode("result = Symbol.__class__")
