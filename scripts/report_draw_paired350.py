"""Validate cumulative provenance and report the three-model primary family."""
import hashlib
import json
from pathlib import Path
from scripts.analyze_confirmatory import holm_adjust

STEMS = ['gpt_oss_20b','gpt_oss_120b','nemotron_3_nano_30b']

def read(path):
    return [json.loads(s) for s in Path(path).read_text().splitlines()]

def main():
    primary, models = [], {}
    cases = read('data/paired/draw_paired/draw_paired350.jsonl')
    expected = {(r['pair_id'],r['label'],m) for r in cases for m in ['self_review','grounded_self_review','nonunique','nonunique_grounding']}
    for stem in STEMS:
        path = Path(f'results/{stem}_draw_paired350_complete.jsonl')
        rows = read(path)
        base = read(f'results/{stem}_draw_paired300_complete.jsonl')
        assert len(rows)==2800 and {(r['pair_id'],r['label'],r['method']) for r in rows}==expected
        assert all(r['status']=='ok' for r in rows)
        assert [{k:v for k,v in r.items() if k!='cohort'} for r in rows[:2400]]==base
        analysis = json.loads(Path(f'results/{stem}_draw_paired350_analysis.json').read_text())
        result = next(r for r in analysis['decision_mcnemar'] if r['hypothesis']=='D4')
        primary.append({**result,'model':stem})
        models[stem] = {'records':len(rows),'original_records_preserved':True,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'summary':analysis['summary']}
    holm_adjust(primary)
    report = {'pairs':350,'cases':700,'extension_pairs':50,'new_records':1200,'total_records':8400,'review_status':'300 author-reviewed; extension50 pending','selection_timing':'extension selected after original300 outcomes; cumulative analysis post-hoc','primary_family':'FDA DeGro minus grounded self-review across three models','primary_comparisons':primary,'models':models}
    Path('results/draw_paired350_report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='models'},indent=2))

if __name__=='__main__': main()
