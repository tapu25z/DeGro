"""Source coverage audit candidate; consumes only public problem/spec fields."""
import json
from .pilot import build_prompt

AUDIT_RULE = '''
Audit procedure (reason internally, return only the requested JSON):
1. Compare EVERY factual condition in the original problem with the current constraints, using algebraic equivalence rather than literal string matching.
2. If an explicit condition is absent, translate that condition faithfully into one Python-style constraint and quote its exact contiguous source text. A condition need not mention the target directly: relations among other declared variables may determine it together with the existing constraints.
3. The solver verdict describes only the CURRENT formalization. It does not imply that the original source lacks sufficient information. Do not abstain while a source condition remains unrepresented.
4. Variable declarations and domain bounds below are already part of the model. Do not add integrality, positivity, bounds, or a solved target value merely because the question asks for an integer answer. Do not invent conditions to resolve ambiguity.
5. If every source condition is already represented, ABSTAIN even though the target remains ambiguous. Use explicit * for multiplication and % for modular congruences. Preserve signs, coefficients and moduli.
'''

def build_audit_prompt(row):
    # Deliberately no labels, gold answers, missing-constraint metadata or pair IDs.
    return build_prompt('nonunique_grounding', row) + '\n\nAlready enforced variable domains:\n' + json.dumps(row['spec']['variables'], sort_keys=True) + '\n' + AUDIT_RULE
