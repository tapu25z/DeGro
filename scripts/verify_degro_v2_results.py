#!/usr/bin/env python3
"""Verify full experiment keys, first-success provenance, prompts and scores."""
import hashlib,json
from collections import Counter
from pathlib import Path
from datetime import datetime,timezone
from targetcheck.degro_v2 import build_audit_prompt
from targetcheck.pilot import build_prompt,score
ROOT=Path('results/degro_v2')
def read(p): return [json.loads(l) for l in Path(p).read_text().splitlines() if l]
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
protocol=json.loads((ROOT/'protocol.json').read_text())
assert sha(ROOT/'fresh_test100.jsonl')==protocol['new_test_sha256']
for p,h in protocol['code_sha256'].items():
 if not p.endswith('run_degro_v2_experiment.py'): assert sha(p)==h,p
verification={}; families={}
for split,data,methods in [('development80','data/paired/mira_pilot_80.jsonl',['source_coverage_audit_v2']),('fresh_test100',ROOT/'fresh_test100.jsonl',['nonunique_grounding','source_coverage_audit_v2'])]:
 cases={(r['pair_id'],r['label']):r for r in read(data)}
 expected={(n,*k,m) for n in protocol['models'] for k in cases for m in methods}
 final=read(ROOT/f'{split}_complete.jsonl'); keys=[(r['model_name'],r['pair_id'],r['label'],r['method']) for r in final]
 assert len(keys)==len(set(keys)) and set(keys)==expected
 first={}; attempts=read(ROOT/f'{split}_attempts.jsonl')
 for r in attempts:
  if r['status']=='ok':first.setdefault((r['model_name'],r['pair_id'],r['label'],r['method']),r)
 for r,k in zip(final,keys):
  assert r==first[k]; assert r['status']=='ok' and r['model']==protocol['models'][r['model_name']]
  assert r['temperature']==1.0 and r['think']=='medium'
  c=cases[r['pair_id'],r['label']]
  prompt=build_audit_prompt(c) if r['method']=='source_coverage_audit_v2' else build_prompt('nonunique_grounding',c)
  assert r['prompt_sha256']==hashlib.sha256(prompt.encode()).hexdigest()
  assert score(c,r['output'])==r['score']
 verification[split]={'expected':len(expected),'verified':len(final),'attempt_status':dict(Counter(r['status'] for r in attempts)),'first_success_preserved':True,'all_scores_recomputed':True,'config_and_prompt_verified':True}
 for n in protocol['models']:
  for m in methods:
   rs=[r for r in final if r['model_name']==n and r['method']==m]
   key=f'{split}/{n}/{m}'; families[key]={}
   for f in sorted({r['family'] for r in rs}):
    subset=[r for r in rs if r['family']==f]; omissions=[r for r in subset if r['label']=='OMISSION']; under=[r for r in subset if r['label']=='UNDERSPECIFIED'];adds=[r for r in subset if r['score']['is_add']]
    families[key][f]={'cases':len(subset),'FDA_percent':100*sum(r['score']['correct'] for r in subset)/len(subset),'RSR_percent':100*sum(r['score']['correct_repair'] for r in omissions)/len(omissions),'CAR_percent':100*sum(r['score']['is_abstain'] for r in under)/len(under),'unsupported_adds':sum(r['score']['unsupported_repair'] for r in adds),'all_adds':len(adds)}
old=[r for p in ['mira_pilot_80','mira_heldout_100','mira_confirmatory_remaining_120'] for r in read(f'data/paired/{p}.jsonl')];fresh=read(ROOT/'fresh_test100.jsonl')
assert not {r['pair_id'] for r in old}&{r['pair_id'] for r in fresh}
assert not {r['problem'] for r in old}&{r['problem'] for r in fresh}
assert len({r['problem'] for r in fresh})==200
result={'completed_utc':datetime.now(timezone.utc).isoformat(),'splits':verification,'new_test_overlap':{'original_pair_ids':0,'exact_problem_text':0},'output_sha256':{str(p):sha(p) for p in ROOT.glob('*complete.jsonl')},'analysis_sha256':sha(ROOT/'analysis.json'),'runner_hashes':{'protocol_initial':protocol['code_sha256']['scripts/run_degro_v2_experiment.py'],'final_transport_runner':sha('scripts/run_degro_v2_experiment.py')}}
(ROOT/'verification.json').write_text(json.dumps(result,indent=2)+'\n');(ROOT/'by_family.json').write_text(json.dumps(families,indent=2)+'\n')
print(json.dumps(result,indent=2))
