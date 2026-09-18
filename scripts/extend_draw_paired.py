"""Lock a disjoint 50-pair extension and a provenance-preserving combined cohort."""
import json
from collections import Counter
from pathlib import Path
from build_draw_paired import read_jsonl, review_row, sha256, write_jsonl
from materialize_draw_paired_provisional import _allocate, _cases, _rank, _validate_oracle

ROOT = Path('data/paired/draw_paired')
SEED = 20260919

def main():
    base = list(read_jsonl(ROOT/'draw_paired.jsonl'))
    excluded = {r['source_index'] for r in base}
    remaining = [r for r in read_jsonl(ROOT/'candidates.jsonl') if not r['span_proposal']['flags'] and r['source_index'] not in excluded]
    split_counts = Counter(r['split'] for r in remaining)
    allocation = _allocate(dict(split_counts), 50)
    selected = []
    for split,n in sorted(allocation.items()):
        selected.extend(sorted((r for r in remaining if r['split']==split),key=lambda r:_rank(r['candidate_id'],SEED))[:n])
    selected.sort(key=lambda r:_rank(r['candidate_id'],SEED))
    assert len(selected)==50 and not ({r['source_index'] for r in selected}&excluded)
    cases = [c for r in selected for c in _cases(r)]
    for c in cases: _validate_oracle(c)
    new_path = ROOT/'draw_paired_extension50.jsonl'
    review_path = ROOT/'draw_paired_extension50_review.jsonl'
    combined_path = ROOT/'draw_paired350.jsonl'
    if new_path.exists():
        assert list(read_jsonl(new_path))==cases, 'locked extension differs; refusing overwrite'
        return
    write_jsonl(new_path,cases)
    write_jsonl(review_path,(review_row(r,i) for i,r in enumerate(selected,1)))
    combined = [{**r,'cohort':'original300','dataset_stage':'HUMAN_REVIEWED_POST_INFERENCE'} for r in base]+[{**r,'cohort':'extension50'} for r in cases]
    write_jsonl(combined_path,combined)
    manifest = {'stage':'MIXED_REVIEW_STATUS','base_pairs':300,'extension_pairs':50,'pairs':350,'cases':700,'seed':SEED,'remaining_clean_pool':len(remaining),'extension_split_counts':dict(Counter(r['split'] for r in selected)),'base_sha256':sha256(ROOT/'draw_paired.jsonl'),'extension_sha256':sha256(new_path),'combined_sha256':sha256(combined_path),'review_packet':str(review_path),'human_review_complete':False,'selection':'disjoint source indices; clean proposals; proportional split allocation; seeded SHA256 rank; extension chosen after original300 outcomes'}
    (ROOT/'draw_paired350.manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest,indent=2))

if __name__=='__main__': main()
