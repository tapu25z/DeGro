"""Checks for the locked, post-hoc 50-pair extension (not human approval)."""
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'data/paired/draw_paired'

def rows(name):
    return [json.loads(s) for s in (ROOT / name).read_text().splitlines()]

def test_extension_is_disjoint_and_balanced():
    base = rows('draw_paired.jsonl')
    extension = rows('draw_paired_extension50.jsonl')
    assert len(base) == 600 and len(extension) == 100
    assert not ({r['source_index'] for r in base} & {r['source_index'] for r in extension})
    assert Counter(r['label'] for r in extension) == {'OMISSION':50,'UNDERSPECIFIED':50}
    assert len({r['source_index'] for r in extension}) == 50
    by_pair = {}
    for r in extension:
        by_pair.setdefault(r['pair_id'], []).append(r)
    for pair in by_pair.values():
        assert len(pair) == 2
        assert pair[0]['spec'] == pair[1]['spec']

def test_combined_preserves_base_and_has_truthful_review_status():
    combined = rows('draw_paired350.jsonl')
    manifest = json.loads((ROOT/'draw_paired350.manifest.json').read_text())
    assert len(combined) == 700
    assert manifest['pairs'] == 350
    assert manifest['combined_sha256'] == hashlib.sha256((ROOT/'draw_paired350.jsonl').read_bytes()).hexdigest()
    assert Counter(r['cohort'] for r in combined) == {'original300':600,'extension50':100}
    original = [{k:v for k,v in r.items() if k not in {'cohort','dataset_stage'}} for r in combined[:600]]
    base = [{k:v for k,v in r.items() if k not in {'cohort','dataset_stage'}} for r in rows('draw_paired.jsonl')]
    assert original == base
    packet = rows('draw_paired_extension50_review.jsonl')
    assert len(packet) == 50
    assert manifest['human_review_complete'] == all(r['review']['status'] == 'APPROVE' for r in packet)
