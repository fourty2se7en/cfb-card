import json,glob,os
K=('market','pick','line','price','tier','shadow','rule')
cur={os.path.basename(f)[:-5]:json.load(open(f)) for f in glob.glob('cur/sports/fbs/picks/*.json')}
new={os.path.basename(f)[len('sports_fbs_picks__'):-5]:json.load(open(f)) for f in glob.glob('x/docs14/sports_fbs_picks__2026-11-14_*.json')}
def key(i,d): return (d.get('game'), d.get('rule'), d.get('market'), d.get('stat') if '_prop_' in i else None, d.get('player'))
ck={key(i,d):i for i,d in cur.items()}; nk={key(i,d):i for i,d in new.items()}
assert len(ck)==len(cur) and len(nk)==len(new), (len(ck),len(cur),len(nk),len(new))
def show(d): return f"{d.get('pick')} {d.get('price')} {d.get('tier')} {'shadow' if d.get('shadow') else 'CARD'} [{d.get('rule')}]"
plan=dict(create=[],delete=[],update=[],keep=[])
for k,i in nk.items():
    n=new[i]
    if k not in ck: plan['create'].append((i,i)); continue
    c=cur[ck[k]]
    diff=[f for f in ('pick','line','tier','shadow') if c.get(f)!=n.get(f) and not (f=='line' and c.get(f) is not None and n.get(f) is not None and float(c[f])==float(n[f]))]
    if diff: plan['update'].append((ck[k],i,diff))
    else: plan['keep'].append((ck[k],i))
for k,i in ck.items():
    if k not in nk: plan['delete'].append(i)
for t in ('create','update','delete'):
    print(t.upper(),len(plan[t]))
    for x in plan[t]:
        if t=='create': print('  ',x[0][11:],'|',show(new[x[1]]))
        elif t=='delete': print('  ',x[11:],'|',show(cur[x]))
        else: print('  ',x[0][11:],x[2],'|',show(cur[x[0]]),'->',show(new[x[1]]),cur[x[0]].get('line'),'->',new[x[1]].get('line'))
print('KEEP',len(plan['keep']))
json.dump(plan,open('plan.json','w'))
