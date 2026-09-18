"""Promote the author-approved extension without changing model inputs or scores."""
import json
from datetime import datetime, timezone
from pathlib import Path
from scripts.build_draw_paired import read_jsonl, sha256, write_jsonl
from targetcheck.pilot import build_prompt

ROOT = Path('data/paired/draw_paired')
METHODS = ['self_review','grounded_self_review','nonunique','nonunique_grounding']
STEMS = ['gpt_oss_20b','gpt_oss_120b','nemotron_3_nano_30b']

def main():
    original = list(read_jsonl(ROOT/'draw_paired_extension50.jsonl'))
    reviewed = list(read_jsonl(ROOT/'draw_paired_extension50_reviewed.jsonl'))
    lookup = {(r['pair_id'],r['label']):r for r in reviewed}
    assert len(original)==len(reviewed) and len(original)>0
    for old in original:
        new = lookup[(old['pair_id'],old['label'])]
        assert {k:v for k,v in old.items() if k!='dataset_stage'}==new
        for method in METHODS: assert build_prompt(method,old)==build_prompt(method,new)
    packet = list(read_jsonl(ROOT/'draw_paired_extension50_review.jsonl'))
    assert sum(r['review']['status']=='APPROVE' for r in packet)==len(reviewed)//2 and all(r['review']['status'] in {'APPROVE','REJECT'} for r in packet)
    combined = list(read_jsonl(ROOT/'draw_paired350.jsonl'))
    for row in combined: row['dataset_stage']='HUMAN_REVIEWED_POST_INFERENCE'
    write_jsonl(ROOT/'draw_paired350.jsonl',combined)
    manifest_path = ROOT/'draw_paired350.manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest.update(stage='FROZEN_HUMAN_REVIEWED_POST_INFERENCE',human_review_complete=True,frozen=True,
                    reviewed_at_utc=datetime.now(timezone.utc).isoformat(),reviewer='author',
                    review_status_counts={'APPROVE':len(combined)//2,'REJECT':manifest.get('excluded_pairs',0)},combined_sha256=sha256(ROOT/'draw_paired350.jsonl'),
                    extension_review_packet_sha256=sha256(ROOT/'draw_paired_extension50_review.jsonl'),
                    review_timing='Both cohorts author-reviewed after their respective inference; extension selected after original300 outcomes')
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    for stem in STEMS:
        for suffix in ['draw_extension50_complete','draw_paired350_complete']:
            path=Path(f'results/{stem}_{suffix}.jsonl')
            rows=list(read_jsonl(path))
            before=[r['score'] for r in rows]
            for row in rows: row['dataset_stage']='HUMAN_REVIEWED_POST_INFERENCE'
            assert [r['score'] for r in rows]==before
            write_jsonl(path,rows)
    print(f'{len(combined)//2} retained author-reviewed pairs frozen; prompts, responses and scores unchanged.')

if __name__=='__main__': main()
