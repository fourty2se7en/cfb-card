import sys, json, gzip
from datetime import datetime
import os; R=os.environ.get('REPO','/home/claude/cfb-card'); sys.path.insert(0,R+'/odds'); sys.path.insert(0,R+'/season')
import read as RD, t222_college as TC
day, yf = sys.argv[1], sys.argv[2]
ev = json.load(gzip.open(f'{R}/season/data/espn/ncaaw/{day}/scoreboard_final.json.gz'))['events']
odds = RD.build('ncaaw', day); E={}
for e in ev:
    c = {x['homeAway']: x['team'] for x in e['competitions'][0]['competitors']}; t = datetime.fromisoformat(e['date'].replace('Z','+00:00')); best=None
    for k,g in odds.items():
        if not g.get('close'): continue
        if abs((datetime.fromisoformat(g['commence'].replace('Z','+00:00'))-t).total_seconds())>3*3600: continue
        s1=(TC.sim(g['away'],c['away'])+TC.sim(g['home'],c['home']), min(TC.sim(g['away'],c['away']),TC.sim(g['home'],c['home'])))
        if s1[0]>=1.2 and s1[1]>=0.7 and (best is None or s1[0]>best[0]): best=(s1[0],g)
    if best: E[e['id']]=best[1]
z=lambda v:'' if v is None else str(v)
out=[]; n=0
for l in open(yf).read().strip().splitlines():
    f=l.split('|')
    g=E.get(f[1])
    if g and not f[16]:
        cl=g['close']; op=g.get('open') or cl
        ml=lambda v: v if v is not None and 100<=abs(v)<=5000 else None
        f[16]=','.join(z(v) for v in (op.get('spread_home'),cl.get('spread_home'),op.get('total'),cl.get('total'),ml(cl.get('ml_home')),ml(cl.get('ml_away')))); n+=1
    out.append('|'.join(f))
open(yf,'w').write('\n'.join(out)+'\n'); print('filled',n)
