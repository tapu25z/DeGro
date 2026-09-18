"""Keep original inference identifiers when repairing sentence segmentation."""
import json
from pathlib import Path
from targetcheck import ModelSpec, check_target_determinacy
from build_draw_paired import convert_row, propose_source_span, review_row, write_jsonl

old = [json.loads(x) for x in Path('results/gpt_oss_20b_draw_paired_provisional300_complete.jsonl').read_text().splitlines()]
ids = sorted({r['pair_id'] for r in old})
raw = {str(r['source_index']): r for r in map(json.loads, Path('data/draw1k/draw1k.jsonl').read_text().splitlines()) if r['split'] in {'train','dev'}}
selected = []
for candidate_id in ids:
    _, source_index, index, target = candidate_id.split('/')
    row = raw[source_index]
    candidate, _ = convert_row(row)
    index = int(index)-1
    expressions = candidate['normalized_equations']
    base = candidate['base_spec']
    base['target'] = target
    base['constraints'] = [{'id':f'c{i+1}','expression':e,'source_span':None,'provenance':'EXPLICIT_TEXT'} for i,e in enumerate(expressions) if i != index]
    full_raw = {**base,'constraints':[{'id':f'c{i+1}','expression':e} for i,e in enumerate(expressions)]}
    gold = check_target_determinacy(ModelSpec.from_dict(full_raw)).target_value
    candidate.update(candidate_id=candidate_id,target=target,gold_target=gold,removed_equation_index=index,base_spec=base,missing_constraint={'id':f'c{index+1}','expression':expressions[index],'source_span':None,'provenance':'EXPLICIT_TEXT'},span_proposal=propose_source_span(row,index))
    selected.append(review_row(candidate))
write_jsonl(Path('data/paired/draw_paired/draw_paired_provisional_300_review.jsonl'),selected)
print(len(selected))
