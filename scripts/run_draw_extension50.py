"""Run the locked extension with resumable workers; merge complete results only."""
import concurrent.futures
import glob
import hashlib
import json
import subprocess
from pathlib import Path
from datetime import datetime, timezone

PY = str(Path.cwd()/'.venv/bin/python')
DATA = 'data/paired/draw_paired/draw_paired_extension50.jsonl'
MODELS = {'gpt_oss_20b':'gpt-oss:20b','gpt_oss_120b':'gpt-oss:120b','nemotron_3_nano_30b':'nemotron-3-nano:30b'}
METHODS = ['self_review','grounded_self_review','nonunique','nonunique_grounding']
SHARDS = 8

def worker(stem,model,shard,method,offset):
    out = f'results/raw/{stem}_draw_extension50_s{shard}_{method}.jsonl'
    log = Path(f'logs/draw_paired/{stem}_draw_extension50_s{shard}_{method}.log')
    with log.open('a') as stream:
        return subprocess.run([PY,'scripts/run_pilot.py','--data',DATA,'--model',model,'--methods',method,'--num-shards',str(SHARDS),'--shard-index',str(shard),'--account-offset',str(offset),'--accounts-per-worker','17','--timeout','60','--out',out],stdout=stream,stderr=subprocess.STDOUT).returncode

def main():
    Path('logs/draw_paired').mkdir(parents=True,exist_ok=True)
    from targetcheck.pilot import prompt_hash
    dataset_manifest = json.loads(Path('data/paired/draw_paired/draw_paired350.manifest.json').read_text())
    manifest = {'started_utc':datetime.now(timezone.utc).isoformat(),'data':DATA,'data_sha256':hashlib.sha256(Path(DATA).read_bytes()).hexdigest(),'models':MODELS,'methods':METHODS,'temperature':1.0,'think':'medium','prompt_hash':prompt_hash(),'extension_pairs':dataset_manifest['extension_pairs'],'combined_pairs':dataset_manifest['pairs'],'review':'see dataset manifest','selection_timing':'extension selected after original300 outcomes; cumulative analysis is post-hoc'}
    Path('results/draw_extension50_run_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    jobs = [(stem,model,s,m,i) for i,(stem,model,s,m) in enumerate((stem,model,s,m) for stem,model in MODELS.items() for s in range(SHARDS) for m in METHODS)]
    for wave in range(3):
        print('wave',wave+1,flush=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
            list(pool.map(lambda args:worker(*args),jobs))
    for stem in MODELS:
        out = f'results/{stem}_draw_extension50_complete.jsonl'
        subprocess.run([PY,'scripts/finalize_pilot.py','--data',DATA,'--methods',*METHODS,'--input-glob',f'results/raw/{stem}_draw_extension50_s*.jsonl','--out',out],check=True)
        base = [json.loads(x) for x in Path(f'results/{stem}_draw_paired300_complete.jsonl').read_text().splitlines()]
        new = [json.loads(x) for x in Path(out).read_text().splitlines()]
        reviewed = json.loads(Path('data/paired/draw_paired/draw_paired350.manifest.json').read_text())['human_review_complete']
        stage = 'HUMAN_REVIEWED_POST_INFERENCE' if reviewed else 'PROVISIONAL_AWAITING_HUMAN_REVIEW'
        combined = [{**r,'cohort':'original300'} for r in base]+[{**r,'cohort':'extension50','dataset_stage':stage} for r in new]
        assert len(combined)==dataset_manifest['cases']*4 and len({(r['pair_id'],r['label'],r['method']) for r in combined})==len(combined)
        dest = Path(f'results/{stem}_draw_paired350_complete.jsonl')
        dest.write_text(''.join(json.dumps(r,separators=(',',':'))+'\n' for r in combined))
        with Path(f'results/{stem}_draw_paired350_summary.tsv').open('w') as stream:
            subprocess.run([PY,'scripts/analyze_pilot.py',str(dest)],stdout=stream,check=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        def analyze(stem):
            with Path(f'results/{stem}_draw_paired350_analysis.json').open('w') as stream:
                subprocess.run([PY,'scripts/analyze_confirmatory.py',f'results/{stem}_draw_paired350_complete.jsonl'],stdout=stream,check=True)
        list(pool.map(analyze,MODELS))
    print(f"COMPLETE: {dataset_manifest['pairs']} pairs; see dataset manifest for review status",flush=True)

if __name__=='__main__': main()
