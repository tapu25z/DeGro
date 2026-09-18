"""Apply the author's post-inference exclusions to DRAW data and saved outputs.
Legacy cohort filenames are retained; manifests describe current cardinalities.
No excluded model outputs are copied into the exclusion audit.
"""
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('data/paired/draw_paired')
EXCLUSIONS = ROOT / 'excluded_pair_ids.txt'

def read(path):
    return [json.loads(s) for s in path.read_text().splitlines() if s.strip()]

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    excluded = set(EXCLUSIONS.read_text().splitlines())
    assert len(excluded) == 50
    current = read(ROOT/'draw_paired350.jsonl')
    found = {r['pair_id'] for r in current} & excluded
    assert found == excluded or not found, sorted(excluded-found)
    audit_path = ROOT/'exclusion_audit.json'
    if not audit_path.exists():
        assert len(current) == 700
        audit = {'reviewer':'author','reviewed_at_utc':datetime.now(timezone.utc).isoformat(),
                 'reason':'Author requested exclusion after data re-review; no item-level rationale supplied.',
                 'timing':'post-inference; exclusions were requested after model results were available',
                 'excluded_pairs':sorted(excluded),'original_pairs':350,'retained_pairs':300,
                 'excluded_by_cohort':dict(Counter(r['cohort'] for r in current if r['pair_id'] in excluded and r['label']=='OMISSION')),
                 'removed_records_by_file':{}}
    else:
        audit = json.loads(audit_path.read_text())
    for path in list(ROOT.glob('*.jsonl')) + list(Path('results').rglob('*.jsonl')):
        lines = path.read_text().splitlines(keepends=True)
        rows = [json.loads(line) for line in lines if line.strip()]
        if path.parent == ROOT and rows and 'candidate_id' in rows[0]:
            changed = False
            for row in rows:
                if row.get('candidate_id') in excluded:
                    if path.name != 'candidates.jsonl':
                        row.setdefault('review',{}).update(status='REJECT',reviewer='author',notes='Excluded by author after data re-review; see exclusion_audit.json.')
                    row['excluded_from_evaluation'] = True
                    changed = True
            if changed:
                path.write_text(''.join(json.dumps(r,separators=(',',':'))+'\n' for r in rows))
            continue
        kept = [line for line in lines if not line.strip() or json.loads(line).get('pair_id') not in excluded]
        removed = len(lines)-len(kept)
        if removed:
            path.write_text(''.join(kept))
            audit['removed_records_by_file'][str(path)] = removed
    for path in Path('results').glob('*.csv'):
        with path.open(newline='') as f:
            reader = csv.DictReader(f); fields=reader.fieldnames; rows=list(reader)
        kept=[r for r in rows if r.get('pair_id') not in excluded]
        if len(kept)!=len(rows):
            with path.open('w',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=fields); writer.writeheader(); writer.writerows(kept)
            audit['removed_records_by_file'][str(path)] = len(rows)-len(kept)
    def clean(value):
        if isinstance(value,list):
            return [clean(v) for v in value if not (isinstance(v,dict) and v.get('pair_id') in excluded)]
        if isinstance(value,dict):
            return {k:clean(v) for k,v in value.items() if k not in excluded}
        return value
    for name in ['pruned_50_tests_multimodel.json','degro_failure_candidates.json']:
        path=Path('results')/name
        if path.exists(): path.write_text(json.dumps(clean(json.loads(path.read_text())),indent=2)+'\n')
    candidate_manifest_path = ROOT/'candidate_manifest.json'
    candidate_manifest = json.loads(candidate_manifest_path.read_text())
    candidate_manifest.update(candidate_sha256=digest(ROOT/'candidates.jsonl'),review_packet_sha256=digest(ROOT/'review_packet.jsonl'),excluded_pairs=50,exclusion_audit=str(audit_path))
    candidate_manifest_path.write_text(json.dumps(candidate_manifest,indent=2)+'\n')
    for path in ROOT.glob('*.manifest.json'):
        manifest=json.loads(path.read_text()); dataset=path.with_name(path.name.replace('.manifest.json','.jsonl'))
        if dataset.exists() and 'paired' in dataset.name:
            rows=read(dataset); pairs={r['pair_id'] for r in rows}
            manifest.update(pairs=len(pairs),cases=len(rows),exclusion_audit=str(audit_path),exclusion_ids_sha256=digest(EXCLUSIONS))
            for field in ['output_sha256','sha256']:
                if field in manifest: manifest[field]=digest(dataset)
            if 'pairs_by_split' in manifest:
                manifest['pairs_by_split']=dict(Counter(r['source_split'] for r in rows if r['label']=='OMISSION'))
            if 'oracle_score_checks' in manifest: manifest['oracle_score_checks']=len(rows)
            if 'candidate_sha256' in manifest: manifest['candidate_sha256']=digest(ROOT/'candidates.jsonl')
            if 'cohort_review_packet' in manifest: manifest['cohort_review_packet_sha256']=digest(Path(manifest['cohort_review_packet']))
            review=manifest.get('review_packet')
            if review and Path(review).exists():
                manifest['review_packet_sha256']=digest(Path(review))
                manifest['review_status_counts']=dict(Counter(r['review']['status'] for r in read(Path(review))))
            if dataset.name=='draw_paired350.jsonl':
                manifest.update(original_pairs=350,excluded_pairs=50,combined_sha256=digest(dataset),
                    base_pairs=sum(r['cohort']=='original300' for r in rows)//2,
                    extension_pairs=sum(r['cohort']=='extension50' for r in rows)//2,
                    base_sha256=digest(ROOT/'draw_paired.jsonl'),extension_sha256=digest(ROOT/'draw_paired_extension50.jsonl'),
                    extension_review_packet_sha256=digest(ROOT/'draw_paired_extension50_review.jsonl'),
                    review_status_counts={'APPROVE':300,'REJECT':50},
                    retained_split_counts=dict(Counter(r['source_split'] for r in rows if r['label']=='OMISSION')))
            path.write_text(json.dumps(manifest,indent=2)+'\n')
    audit_path.write_text(json.dumps(audit,indent=2)+'\n')
    retained=read(ROOT/'draw_paired350.jsonl')
    assert len(retained)==600 and not ({r['pair_id'] for r in retained}&excluded)
    print(json.dumps({k:v for k,v in audit.items() if k not in {'excluded_pairs','removed_records_by_file'}},indent=2))

if __name__=='__main__': main()
