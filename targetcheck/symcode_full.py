from __future__ import annotations

import ast
import re
import subprocess
import sys


class SymCodeExecutionError(RuntimeError):
    pass


_BANNED_CALLS = {
    "breakpoint", "compile", "eval", "exec", "globals", "help", "input",
    "locals", "open", "vars", "__import__",
}


def extract_python_code(text: str) -> str:
    blocks = re.findall(r"```python\s*(.*?)\s*```", text, re.I | re.S)
    if blocks:
        return blocks[-1]
    raise SymCodeExecutionError("response does not contain one fenced Python block")


def validate_code(code: str) -> ast.Module:
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as exc:
        raise SymCodeExecutionError(f"SyntaxError: {exc}") from exc
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [alias.name for alias in node.names]
            if isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            if any(name != "sympy" and not name.startswith("sympy.") for name in names):
                raise SymCodeExecutionError("only SymPy imports are allowed")
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            raise SymCodeExecutionError("dunder names are disallowed")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise SymCodeExecutionError("dunder attributes are disallowed")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _BANNED_CALLS:
            raise SymCodeExecutionError(f"call is disallowed: {node.func.id}")
    return tree


def execute_symcode_full(code: str, timeout_s: int = 12) -> str:
    validate_code(code)
    wrapper = "import sys\ncode=sys.stdin.read()\nscope={'__builtins__':__builtins__}\nexec(compile(code,'<symcode>','exec'),scope,scope)\n"
    try:
        completed = subprocess.run(
            [sys.executable, "-I", "-c", wrapper],
            input=code,
            text=True,
            capture_output=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise SymCodeExecutionError(f"TimeoutError: execution exceeded {timeout_s}s") from exc
    if completed.returncode != 0:
        error = completed.stderr.strip().splitlines()[-1] if completed.stderr.strip() else f"exit {completed.returncode}"
        raise SymCodeExecutionError(error[:600])
    value = completed.stdout.strip()
    if not value:
        raise SymCodeExecutionError("script produced no stdout")
    return value.splitlines()[-1].strip()
