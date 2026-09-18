#!/usr/bin/env python3
"""One frozen candidate, complete development audit and independent new test."""
import concurrent.futures as cf
import hashlib,json,random,time,os
from pathlib import Path
from datetime import datetime,timezone
from targetcheck.degro_v2 import build_audit_prompt
from targetcheck.pilot import build_prompt,OUTPUT_SCHEMA,parse_decision,score
from targetcheck.providers import OllamaCloudClient,load_api_keys
from scripts.analyze_confirmatory import rate,mcnemar,paired_cluster_bootstrap_ci,holm_adjust
ROOT=Path('results/degro_v2'); ROOT.mkdir(exist_ok=True)
MODELS={'nano30b':'nemotron-3-nano:30b','gpt120b':'gpt-oss:120b'}
SEED=2026091701

def digest(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return [json.loads(l) for l in Path(p).read_text().splitlines() if l]
def prepare():
    excluded=set(); excluded_problems=set()
    for p in ['data/paired/mira_pilot_80.jsonl','data/paired/mira_heldout_100.jsonl','data/paired/mira_confirmatory_remaining_120.jsonl']:
        excluded.update(r['pair_id'] for r in read(p)); excluded_problems.update(r['problem'] for r in read(p))
    # The original 300 exhaust solver-compatible MIRA instances. Generate a
    # separately labelled synthetic stress test; never describe it as new MIRA.
    from targetcheck.modelspec import ModelSpec,Variable,Constraint
    from targetcheck.determinacy import check_target_determinacy,CheckStatus
    from dataclasses import asdict
    rng=random.Random(SEED); pairs=[]; buckets={f:[] for f in ['linear_system_separator','graph_path_sums','crt_reconstruction','rankdef_linear_shared']}
    seen_problems=set()
    for family in buckets:
        while len(buckets[family])<25:
            i=len(buckets[family]); names=['x','y'] if family=='linear_system_separator' else ['e01','e12','e20'] if family=='graph_path_sums' else ['x'] if family=='crt_reconstruction' else ['x','y','z']
            golds={n:rng.randint(-30,30) for n in names}; expressions=[]; spans=[]
            if family=='crt_reconstruction':
                mods=rng.sample([3,5,7,11,13,17,19],3); upper=mods[0]*mods[1]*mods[2]; golds['x']=rng.randrange(upper)
                variables=(Variable('x','Int',lower=0,upper=upper-1),)
                for m in mods:
                    expressions.append(f'x % {m} == {golds["x"]%m}'); spans.append(f'x ≡ {golds["x"]%m} (mod {m}).')
            else:
                variables=tuple(Variable(n,'Int') for n in names)
                coeffs=[[1,1,0],[0,1,1],[1,0,1]] if family=='graph_path_sums' else [[rng.randint(-7,7) for n in names] for _ in names]
                for cs in coeffs:
                    rhs=sum(c*golds[n] for c,n in zip(cs,names))
                    lhs=' + '.join(f'({c}) * {n}' for c,n in zip(cs,names) if c) or '0'
                    expressions.append(f'{lhs} == {rhs}'); spans.append(f'{lhs} = {rhs}.')
            constraints=tuple(Constraint(f'c{j}',e,t,'EXPLICIT_TEXT') for j,(e,t) in enumerate(zip(expressions,spans)))
            base=ModelSpec(variables,constraints[:-1],names[0],{'family':family,'source':'new synthetic stress test'})
            full=ModelSpec(variables,constraints,names[0],base.metadata)
            if check_target_determinacy(base).status!=CheckStatus.AMBIGUOUS: continue
            check=check_target_determinacy(full)
            if check.status!=CheckStatus.DETERMINATE or check.target_value!=golds[names[0]]: continue
            shared={'pair_id':f'v2synthetic-{family}-{i:03d}','family':family,'difficulty':len(names),'spec':asdict(base),'gold_target':golds[names[0]]}
            question=f'Find the integer value of {names[0]}.'
            indices=list(range(len(spans))); rng.shuffle(indices)
            omission={**shared,'label':'OMISSION','problem':' '.join([spans[j] for j in indices]+[question]),'missing_constraint':asdict(constraints[-1])}
            under={**shared,'label':'UNDERSPECIFIED','problem':' '.join([spans[j] for j in indices if j<len(spans)-1]+[question]),'missing_constraint':None}
            if omission['problem'] in excluded_problems|seen_problems or under['problem'] in excluded_problems|seen_problems: continue
            seen_problems.update([omission['problem'],under['problem']])
            buckets[family].append((omission,under))
    pairs=[p for v in buckets.values() for p in v]; rng.shuffle(pairs)
    path=ROOT/'fresh_test100.jsonl'
    path.write_text(''.join(json.dumps(r)+'\n' for p in pairs for r in p))
    assert not {r['pair_id'] for r in read(path)} & excluded
    manifest={'created_utc':datetime.now(timezone.utc).isoformat(),'candidate':'source_coverage_audit_v2','models':MODELS,'temperature':1.0,'think':'medium','selection':'one candidate chosen from pilot80 error analysis; no adaptive search or test-based selection','new_test':str(path),'new_test_sha256':digest(path),'excluded_original_pairs':len(excluded),'test_pairs':100,'families':{f:25 for f in buckets},'test_source':'newly generated synthetic stress test; original MIRA pool exhausted','selection_seed':SEED,'retry':'up to 3 transport/parse attempts; first valid response retained regardless of score','metrics':['RSR','CAR','FDA','ORR'],'primary':'new-test FDA candidate minus concurrently rerun original DeGro; two-model Holm adjustment; pair bootstrap10000','code_sha256':{p:digest(p) for p in ['targetcheck/degro_v2.py',__file__,'targetcheck/pilot.py']}}
    (ROOT/'protocol.json').write_text(json.dumps(manifest,indent=2)+'\n')

def run(split,data,methods):
    cases=read(data); keys=load_api_keys(Path('api.txt')); out=ROOT/f'{split}_attempts.jsonl'
    prior=read(out) if out.exists() else []
    done={(r['model_name'],r['pair_id'],r['label'],r['method']) for r in prior if r['status']=='ok'}
    jobs=[(name,model,r,m) for name,model in MODELS.items() for r in cases for m in methods if (name,r['pair_id'],r['label'],m) not in done]
    def infer(job):
        name,model,row,method=job
        prompt=build_audit_prompt(row) if method=='source_coverage_audit_v2' else build_prompt('nonunique_grounding',row)
        config={'model_name':name,'model':model,'pair_id':row['pair_id'],'label':row['label'],'family':row['family'],'difficulty':row['difficulty'],'method':method,'temperature':1.0,'think':'medium','prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest(),'split':split}
        offset=int(hashlib.sha256((name+row['pair_id']+method).encode()).hexdigest()[:8],16)%len(keys)
        client=OllamaCloudClient(keys[offset:]+keys[:offset],timeout_s=90)
        attempts=[]
        for attempt in range(3):
            start=time.monotonic()
            rec={**config,'attempt':attempt+1}
            try:
                response=client.chat(model,[{'role':'user','content':prompt}],format_schema=OUTPUT_SCHEMA,options={'temperature':1.0},think='medium')
                output=parse_decision(response.get('message',{}).get('content',''))
                rec.update(status='ok',output=output,response=response)
            except Exception as exc: rec.update(status='error',error_type=type(exc).__name__,error=str(exc)[:500])
            rec['wall_seconds']=time.monotonic()-start; rec['account_attempts']=[a.__dict__ for a in client.last_attempts]; attempts.append(rec)
            if rec['status']=='ok' or (rec.get('error_type')=='OllamaCloudError' and rec.get('account_attempts') and all(a.get('status') in (None,429) for a in rec['account_attempts']) and any(a.get('status')==429 for a in rec['account_attempts'])): break
        return row,attempts
    with out.open('a') as stream,cf.ThreadPoolExecutor(max_workers=int(os.environ.get("DEGRO_WORKERS", "4"))) as pool:
        futures=[pool.submit(infer,j) for j in jobs]
        for i,f in enumerate(cf.as_completed(futures),1):
            row,attempts=f.result()
            # Z3 scoring stays in this single main thread.
            for rec in attempts:
                if rec['status']=='ok': rec['score']=score(row,rec['output'])
                stream.write(json.dumps(rec)+'\n')
            stream.flush(); print(f'{split}: {len(done)+i}/{len(done)+len(jobs)} {attempts[-1]["status"]}',flush=True)
            last=attempts[-1]
            if last['status']=='error' and last.get('account_attempts') and all(a.get('status') in (None,429) for a in last['account_attempts']) and any(a.get('status')==429 for a in last['account_attempts']):
                for pending in futures: pending.cancel()
                raise SystemExit('Service returned429 on all accounts; stopped. Resume when service accepts requests.')
    valid={}
    for r in read(out):
        if r['status']=='ok': valid.setdefault((r['model_name'],r['pair_id'],r['label'],r['method']),r)
    assert len(valid)==len(cases)*len(MODELS)*len(methods), 'incomplete experiment; rerun to resume errors only'
    (ROOT/f'{split}_complete.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in valid.values()))
    return list(valid.values())

def summarize(dev,test):
    comparisons=[]; result={}
    baseline={name:[r for r in read(f'results/{prefix}_mira_pilot80_current_four_methods_complete.jsonl') if r['method']=='nonunique_grounding'] for name,prefix in [('nano30b','nemotron_3_nano_30b'),('gpt120b','gpt_oss_120b')]}
    for name in MODELS:
        dr=[r for r in dev if r['model_name']==name]; tr=[r for r in test if r['model_name']==name]
        measures=lambda rs:{m:100*rate(rs,m) for m in ['RSR','CAR','FDA','ORR']}
        comp=mcnemar(tr,'FDA','source_coverage_audit_v2','nonunique_grounding'); comp['model']=name
        comp['delta_ci95']=paired_cluster_bootstrap_ci(tr,'FDA','source_coverage_audit_v2','nonunique_grounding',10000,SEED); comparisons.append(comp)
        result[name]={'development_original':measures(baseline[name]),'development_candidate':measures(dr),'fresh_test':{m:measures([r for r in tr if r['method']==m]) for m in ['nonunique_grounding','source_coverage_audit_v2']}}
    holm_adjust(comparisons)
    (ROOT/'analysis.json').write_text(json.dumps({'metrics_percent':result,'fresh_test_comparisons':comparisons,'note':'Exploratory follow-up on fresh instances on a newly generated synthetic stress test; no replacement of historical confirmatory results.'},indent=2)+'\n')
    text=['# DeGro source coverage audit v2','One candidate frozen before fresh-test inference. All responses retained; old confirmatory results unchanged.','Fresh test: 100 disjoint pairs, 25 per family, generated synthetic instances; this is not an external benchmark.','']
    for name,vals in result.items(): text.extend([f'## {name}',json.dumps(vals,indent=2),json.dumps(next(c for c in comparisons if c['model']==name),indent=2),''])
    (ROOT/'report.md').write_text('\n'.join(text))
    print(json.dumps({'metrics':result,'comparisons':comparisons},indent=2),flush=True)

if __name__=='__main__':
    if not (ROOT/'protocol.json').exists(): prepare()
    dev=run('development80','data/paired/mira_pilot_80.jsonl',['source_coverage_audit_v2'])
    test=run('fresh_test100',ROOT/'fresh_test100.jsonl',['nonunique_grounding','source_coverage_audit_v2'])
    summarize(dev,test)
