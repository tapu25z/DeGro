"""Rescore unchanged responses and replace the two corrected-source pairs."""
import glob
import json
from pathlib import Path
from targetcheck.pilot import score

cases = [json.loads(x) for x in Path('data/paired/draw_paired/draw_paired.jsonl').read_text().splitlines()]
lookup = {(r['pair_id'], r['label']): r for r in cases}
corrected = {'draw-paired/150329/1/plywood', 'draw-paired/39411/1/x'}
for stem in ['gpt_oss_20b', 'gpt_oss_120b', 'nemotron_3_nano_30b']:
    old = Path(f'results/{stem}_draw_paired_provisional300_complete.jsonl')
    records = {}
    for line in old.read_text().splitlines():
        row = json.loads(line)
        if row['pair_id'] not in corrected:
            records[(row['pair_id'],row['label'],row['method'])] = row
    for filename in sorted(glob.glob(f'results/raw/draw_paired_corrections/{stem}_*.jsonl')):
        for line in Path(filename).read_text().splitlines():
            row = json.loads(line)
            key = (row['pair_id'],row['label'],row['method'])
            if row['status'] == 'ok':
                records.setdefault(key,row)
    if len(records) != 2400:
        raise ValueError(f'{stem}: only {len(records)}/2400 corrected records')
    for key,row in records.items():
        row['score'] = score(lookup[key[:2]], row['output'])
        row['dataset_stage'] = 'HUMAN_REVIEWED_POST_INFERENCE'
    out = Path(f'results/{stem}_draw_paired300_complete.jsonl')
    out.write_text(''.join(json.dumps(records[k],separators=(',',':'))+'\n' for k in sorted(records)))
    print(stem,len(records))
