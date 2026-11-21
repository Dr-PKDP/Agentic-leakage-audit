"""Statistics for the rerun with a review limit of 2,048 tokens and a revision limit of 512.

Compares results/review_limit_2048 with the principal run and the extended run (review limit 1,024).
Writes results/review_limit_2048/stats.json. No model calls.
"""
import csv,json,math,random,collections
from math import comb
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
L=str(ROOT/"results/review_limit_2048");R=str(ROOT/"results/label_contexts")
C0=str(ROOT/"results/core_contexts/per_input_outcomes.csv")
SEED=20261028;B=5000
def wilson(k,n,z=1.959964):
    p=k/n;d=1+z*z/n;c=(p+z*z/(2*n))/d;h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [round(100*(c-h),1),round(100*(c+h),1)]
def mcn(b,c):
    n=b+c
    if n==0:return 1.0
    k=min(b,c);return min(1.0,2*sum(comb(n,i) for i in range(k+1))/2**n)
rd=lambda f:list(csv.DictReader(open(f)))
agents=['self_review','structure_feedback','evidence_critic','patch_critic/interface_only','patch_critic/evidence_guarded']
def table(rows,paths):
    d={}
    for p in paths:
        rr=[r for r in rows if r['path']==p]
        con=[r for r in rr if r['initial']=='contradicted_contract'];sup=[r for r in rr if r['initial']=='supported']
        rep=sum(r['final']=='supported' for r in con);pre=sum(r['final']=='supported' for r in sup);h=sum(r['final']=='contradicted_contract' for r in sup)
        d[p]={'repair':[rep,len(con),wilson(rep,len(con))],'preserve':[pre,len(sup),wilson(pre,len(sup))],'harmful':h,
          'supported_all':sum(r['final']=='supported' for r in rr),'n':len(rr),'unparse':sum(r['status']!='completed' or r['pipeline']!='assessable' for r in rr)}
    return d
out={}
core_old=rd(C0);core_new=rd(f'{L}/core24/outcomes.csv')
nh_old=rd(f'{R}/nhanes_default/outcomes.csv');nh_new=rd(f'{L}/nhanes/outcomes.csv')
out['core24']={'limit1024':table(core_old,agents),'limit2048':table(core_new,agents)}
out['nhanes']={'limit1024':table(nh_old,agents+['prefix_rule_reviser']),'limit2048':table(nh_new,agents+['prefix_rule_reviser'])}
def paired(old,new,paths):
    O={r['unit']+'|'+r['path']:r for r in old};N={r['unit']+'|'+r['path']:r for r in new};res={}
    for p in paths:
        for init,key in(('contradicted_contract','repair'),('supported','preserve')):
            ks=[k for k in O if k in N and O[k]['path']==p and O[k]['initial']==init]
            b=sum(O[k]['final']!='supported' and N[k]['final']=='supported' for k in ks)
            c=sum(O[k]['final']=='supported' and N[k]['final']!='supported' for k in ks)
            res.setdefault(p,{})[key]={'n':len(ks),'better_with_long':b,'worse_with_long':c,'p':round(mcn(b,c),4)}
    return res
out['paired_core24']=paired(core_old,core_new,agents);out['paired_nhanes']=paired(nh_old,nh_new,agents)
# pooled repair, context-level bootstrap (all agent streams, patch under Gate B)
streams=['self_review','structure_feedback','evidence_critic','patch_critic/evidence_guarded']
def pooled(rows,init='contradicted_contract'):
    m=collections.defaultdict(list)
    for r in rows:
        if r['path'] in streams and r['initial']==init: m[r['context_id']].append(r['final']=='supported')
    return m
rng=random.Random(SEED)
for name,old,new in(('core24',core_old,core_new),('nhanes',nh_old,nh_new)):
    mo,mn=pooled(old),pooled(new);cs=sorted(set(mo)&set(mn))
    def rate(m,s):return sum(sum(m[c]) for c in s)/sum(len(m[c]) for c in s)
    diff=rate(mn,cs)-rate(mo,cs);bs=[]
    for _ in range(B):
        s=[rng.choice(cs) for _ in cs];bs.append(rate(mn,s)-rate(mo,s))
    bs.sort()
    out['pooled_repair_'+name]={'old':round(100*rate(mo,cs),1),'new':round(100*rate(mn,cs),1),'diff_pp':round(100*diff,1),'ci':[round(100*bs[int(.025*B)],1),round(100*bs[int(.975*B)-1],1)],'contexts':len(cs)}
# NHANES agents minus prefix, context level, long run
ctxs=sorted({r['context_id'] for r in nh_new})
def pc(rows,path,init):
    m=collections.defaultdict(list)
    for r in rows:
        if r['path']==path and r['initial']==init: m[r['context_id']].append(r['final']=='supported')
    return {c:sum(v)/len(v) for c,v in m.items()}
cmp={}
for init,name in(('contradicted_contract','repair'),('supported','preservation')):
    pre=pc(nh_new,'prefix_rule_reviser',init)
    for p in agents:
        a=pc(nh_new,p,init);cs=[c for c in ctxs if c in a and c in pre];diff=[a[c]-pre[c] for c in cs];bs=[]
        for _ in range(B):
            s=[rng.choice(diff) for _ in cs];bs.append(sum(s)/len(s))
        bs.sort();cmp.setdefault(name,{})[p]={'diff_pp':round(100*sum(diff)/len(diff),1),'ci':[round(100*bs[int(.025*B)],1),round(100*bs[int(.975*B)-1],1)],'contexts':len(cs)}
out['agent_minus_prefix_long']=cmp
A={r['unit']:r for r in nh_new if r['path']=='patch_critic/interface_only'};G={r['unit']:r for r in nh_new if r['path']=='patch_critic/evidence_guarded'}
pairs=[(A[u],G[u]) for u in A if A[u]['initial']=='supported' and A[u]['status']=='completed' and G[u]['status']=='completed']
b=sum(a['final']=='contradicted_contract' and g['final']!='contradicted_contract' for a,g in pairs);c=sum(a['final']!='contradicted_contract' and g['final']=='contradicted_contract' for a,g in pairs)
out['gate_nhanes_long']={'pairs':len(pairs),'only_B_better':b,'only_A_better':c,'p':round(mcn(b,c),4),'contexts':sorted({a['context_id'] for a,g in pairs if (a['final']=='contradicted_contract')!=(g['final']=='contradicted_contract')})}
Ac={r['unit']:r for r in core_new if r['path']=='patch_critic/interface_only'};Gc={r['unit']:r for r in core_new if r['path']=='patch_critic/evidence_guarded'}
out['gate_core_long_discordant']=sum(Ac[u]['final']!=Gc[u]['final'] for u in Ac)
# truncation
for name,f in(('core24','core24'),('nhanes','nhanes')):
    s=json.load(open(f'{L}/{f}/summary.json'))['requests'];out['requests_'+name]=s
out['requests_old_nhanes']=json.load(open(f'{R}/nhanes_default/summary.json'))['requests']
# outcomes by review-finish unavailable per unit; per-kind NHANES
json.dump(out,open(f'{L}/stats.json','w'),indent=1)
