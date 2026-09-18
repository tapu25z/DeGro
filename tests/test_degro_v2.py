from targetcheck.degro_v2 import build_audit_prompt


def test_audit_prompt_is_independent_of_evaluation_metadata():
    public = {'problem': 'x + y = 10. x = 3. Find x.', 'spec': {'variables': [{'name': 'x', 'sort': 'Int', 'lower': 0, 'upper': 20}, {'name': 'y', 'sort': 'Int'}], 'constraints': [{'id': 'c1', 'expression': 'x + y == 10'}], 'target': 'x'}}
    first = {**public, 'label': 'OMISSION', 'gold_target': 3, 'pair_id': 'one', 'missing_constraint': {'expression': 'x == 3'}}
    second = {**public, 'label': 'UNDERSPECIFIED', 'gold_target': 999, 'pair_id': 'two', 'missing_constraint': None}
    assert build_audit_prompt(first) == build_audit_prompt(second)
    assert 'Already enforced variable domains:' in build_audit_prompt(first)
    assert '"upper": 20' in build_audit_prompt(first)
