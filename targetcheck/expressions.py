from __future__ import annotations

import io
import token
import tokenize
from collections.abc import Collection


class ExpressionNormalizationError(ValueError):
    pass


_CHAR_REPLACEMENTS = str.maketrans(
    {
        "−": "-",  # mathematical minus
        "×": "*",  # multiplication sign
        "·": "*",  # middle dot
        "≤": "<=",
        "≥": ">=",
        "≠": "!=",
    }
)


def _is_open_paren(item: tokenize.TokenInfo) -> bool:
    return item.type == token.OP and item.string == "("


def _is_close_paren(item: tokenize.TokenInfo) -> bool:
    return item.type == token.OP and item.string == ")"


def _is_symbol(item: tokenize.TokenInfo, symbols: Collection[str]) -> bool:
    return item.type == token.NAME and item.string in symbols


def _needs_implicit_multiply(
    left: tokenize.TokenInfo,
    right: tokenize.TokenInfo,
    symbols: Collection[str],
) -> bool:
    left_is_value = left.type == token.NUMBER or _is_symbol(left, symbols) or _is_close_paren(left)
    right_is_value = _is_symbol(right, symbols) or _is_open_paren(right)
    return left_is_value and right_is_value


def normalize_expression(expression: str, symbols: Collection[str]) -> str:
    """Normalize common mathematical notation into the supported Python fragment.

    Multiplication is inserted only where token boundaries and declared symbol names
    make it unambiguous. In particular, an unknown name such as ``xy`` is never
    split into ``x*y``, and scientific-notation tokens such as ``2e01`` are left
    untouched.
    """

    if not isinstance(expression, str):
        raise ExpressionNormalizationError("expression must be a string")

    translated = expression.translate(_CHAR_REPLACEMENTS)
    translated = translated.replace("&&", " and ").replace("||", " or ").replace("^", "**")
    try:
        items = list(tokenize.generate_tokens(io.StringIO(translated).readline))
    except (IndentationError, tokenize.TokenError) as exc:
        raise ExpressionNormalizationError(str(exc)) from exc

    significant = {
        token.NAME,
        token.NUMBER,
        token.OP,
    }
    normalized: list[tuple[int, str]] = []
    previous: tokenize.TokenInfo | None = None
    for item in items:
        if item.type == token.ENDMARKER:
            continue
        if item.type == token.ERRORTOKEN and not item.string.isspace():
            raise ExpressionNormalizationError(f"unsupported character: {item.string!r}")
        if item.type not in significant:
            continue
        if previous is not None and _needs_implicit_multiply(previous, item, symbols):
            normalized.append((token.OP, "*"))
        value = "==" if item.type == token.OP and item.string == "=" else item.string
        normalized.append((item.type, value))
        previous = item

    if not normalized:
        raise ExpressionNormalizationError("expression is empty")
    return tokenize.untokenize(normalized)
