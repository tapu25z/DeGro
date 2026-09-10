import pytest

from targetcheck.pilot import parse_decision


def test_parse_decision_accepts_bare_json():
    assert parse_decision('{"decision":"ABSTAIN","source_span":null,"constraint":null}') == {
        "decision": "ABSTAIN",
        "source_span": None,
        "constraint": None,
    }


def test_parse_decision_accepts_json_code_fence():
    assert parse_decision(
        '```json\n{"decision":"ADD_CONSTRAINT","source_span":"x = 3","constraint":"x == 3"}\n```'
    )["constraint"] == "x == 3"


def test_parse_decision_uses_final_corrected_fence():
    content = """```json
{"decision":"ADD_CONSTRAINT","source_span":"x = 3","-constraint":"x == 3"}
```
Correction:
```json
{"decision":"ADD_CONSTRAINT","source_span":"x = 3","constraint":"x == 3"}
```"""
    assert parse_decision(content)["constraint"] == "x == 3"


def test_parse_decision_rejects_invalid_content():
    with pytest.raises((ValueError, TypeError)):
        parse_decision("not JSON")
