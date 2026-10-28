"""Statistics for the extended run (NHANES-label contexts, thinking-mode comparison).

Reads results/extended_v0_5 and writes results/extended_v0_5/stats.json. No model calls.
"""
import csv,json,math,random,collections
from pathlib import Path
from math import comb
ROOT=Path(__file__).resolve().parents[1]
R=str(ROOT/"results/extended_v0_5")
SEED=20261027;B=5000
def wilson(k,n,z=1.959964):
    p=k/n;d=1+z*z/n;c=(p+z*z/(2*n))/d;h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [round(100*(c-h),1),round(100*(c+h),1)]
def mcnemar(b,c):
    n=b+c
    if n==0:return 1.0
    k=min(b,c);return min(1.0,2*sum(comb(n,i) for i in range(k+1))/2**n)
def load(a): return list(csv.DictReader(open(f'{R}/{a}/outcomes.csv')))
agents=['self_review','structure_feedback','evidence_critic','patch_critic/interface_only','patch_critic/evidence_guarded']
out={}
for arm in ('nhanes_default','nhanes_think_off'):
    rows=load(arm);d={}
    for p in agents+['prefix_rule_reviser']:
        rr=[r for r in rows if r['path']==p]
        con=[r for r in rr if r['initial']=='contradicted_contract'];sup=[r for r in rr if r['initial']=='supported']
        rep=sum(r['final']=='supported' for r in con);pre=sum(r['final']=='supported' for r in sup);harm=sum(r['final']=='contradicted_contract' for r in sup)
        d[p]={'repair':[rep,len(con),round(100*rep/len(con),1),wilson(rep,len(con))],'preserve':[pre,len(sup),round(100*pre/len(sup),1),wilson(pre,len(sup))],'harmful':harm,
              'retained':round(sum(float(r['retained_fraction']) for r in rr if r['retained_fraction'])/max(1,sum(1 for r in rr if r['retained_fraction'])),3)}
    out[arm]=d
rows=load('nhanes_default')
ctxs=sorted({r['context_id'] for r in rows})
def per_ctx(path,init):
    m=collections.defaultdict(list)
    for r in rows:
        if r['path']==path and r['initial']==init: m[r['context_id']].append(r['final']=='supported')
    return {c:sum(v)/len(v) for c,v in m.items()}
rng=random.Random(SEED);cmp={}
for init,name in (('contradicted_contract','repair'),('supported','preservation')):
    pre=per_ctx('prefix_rule_reviser',init)
    for p in agents:
        a=per_ctx(p,init);diff=[a[c]-pre[c] for c in ctxs]
        bs=[]
        for _ in range(B):
            s=[rng.choice(diff) for _ in ctxs];bs.append(sum(s)/len(s))
        bs.sort();cmp.setdefault(name,{})[p]={'difference_pp':round(100*sum(diff)/len(diff),1),'bootstrap_95_pp':[round(100*bs[int(.025*B)],1),round(100*bs[int(.975*B)-1],1)]}
out['agent_minus_prefix_contextlevel']=cmp
# gate A vs B (paired by input and seed)
A={(r['unit']):r for r in rows if r['path']=='patch_critic/interface_only'};G={(r['unit']):r for r in rows if r['path']=='patch_critic/evidence_guarded'}
g={}
for init,key in (('supported','harm'),('contradicted_contract','repair')):
    pairs=[(A[u],G[u]) for u in A if A[u]['initial']==init and A[u]['status']=='completed' and G[u]['status']=='completed']
    if key=='harm':
        b=sum(a['final']=='contradicted_contract' and gg['final']!='contradicted_contract' for a,gg in pairs);c=sum(a['final']!='contradicted_contract' and gg['final']=='contradicted_contract' for a,gg in pairs)
    else:
        b=sum(a['final']!='supported' and gg['final']=='supported' for a,gg in pairs);c=sum(a['final']=='supported' and gg['final']!='supported' for a,gg in pairs)
    ctx=sorted({a['context_id'] for a,gg in pairs if (a['final']=='contradicted_contract')!=(gg['final']=='contradicted_contract')}) if key=='harm' else None
    g[key]={'parseable_pairs':len(pairs),'only_gate_B_better':b,'only_gate_A_better':c,'exact_mcnemar_p':round(mcnemar(b,c),4),'contexts_with_discordance':ctx}
out['gate_A_vs_B']=g
# truncation in NHANES arm: finish reasons from summary
out['nhanes_review_truncated']={a:json.load(open(f'{R}/{a}/summary.json'))['requests']['review']['finish_reasons'] for a in ('nhanes_default','nhanes_think_off')}
# thinking-mode identity
r2=load('nhanes_think_off');a={(r['unit'],r['path']):r['final'] for r in rows};b={(r['unit'],r['path']):r['final'] for r in r2}
out['nhanes_thinking_identical_path_outcomes']=[len(a)-sum(a[k]!=b[k] for k in a),len(a)]
# archetype table
arch=json.load(open(f'{R}/nhanes_default/summary.json'))['by_archetype_path']
out['by_archetype_path']=arch
json.dump(out,open(f'{R}/stats.json','w'),indent=1)
for p in agents+['prefix_rule_reviser']:
    d=out['nhanes_default'][p];print(p,d['repair'][:3],d['repair'][3],d['preserve'][:3],d['harmful'],d['retained'])
print(json.dumps(out['agent_minus_prefix_contextlevel']));print(json.dumps(out['gate_A_vs_B']));print(out['nhanes_review_truncated'],out['nhanes_thinking_identical_path_outcomes'])
