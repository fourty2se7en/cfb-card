import json,os,glob
L='live/sports/nhl/'
live={f[:-5]:json.load(open(L+'picks/'+f)) for f in os.listdir(L+'picks') if not f.startswith('.')}
B={os.path.basename(f)[18:-5]:json.load(open(f)) for f in glob.glob('hub/sports_nhl_picks__*.json')}
def key(d): return (d.get('pick'),d.get('side'),d.get('line'),d.get('tier'),bool(d.get('shadow')),bool(d.get('tt_contradiction')),bool(d.get('contradiction')))
plan=[]
for k in sorted(set(live)|set(B)):
    a,b=live.get(k),B.get(k)
    if a is None: plan.append(('new',k)); continue
    if b is None: plan.append(('del',k)); continue
    if key(a)!=key(b): plan.append(('chg',k))
    # price only: keep live
json.dump(plan,open('plan.json','w'))
for p in plan:
    a,b=live.get(p[1]),B.get(p[1]); d=b or a
    s=lambda x:None if x is None else f"{x['pick']} {x.get('price')} {x['tier']}{' card' if not x.get('shadow') else ' wb'}{' TTflag' if x.get('tt_contradiction') else ''}"
    print(p[0],p[1][11:],'|',s(a),'->',s(b))
print(len(plan))
