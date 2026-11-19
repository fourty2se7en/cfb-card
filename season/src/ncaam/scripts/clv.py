import sys,json,gzip,glob
from datetime import datetime
sys.path[:0]=['/home/claude/season/ncaam/repo/odds','/home/claude/season/ncaam/repo/season']
import read as R, t222_college as TC
DAY=sys.argv[1]; PEND=sys.argv[2]; GO=sys.argv[3]; VER=sys.argv[4]; OUT=sys.argv[5]
ev=json.load(gzip.open(f'/home/claude/season/ncaam/repo/season/data/espn/ncaam/{DAY}/scoreboard_final.json.gz'))['events']
odds=R.build('ncaam',DAY)
esp=[]
for e in ev:
    c={x['homeAway']:x['team'] for x in e['competitions'][0]['competitors']}
    esp.append((e['id'],datetime.fromisoformat(e['date'].replace('Z','+00:00')),c['away'],c['home']))
M={};used=set()
for k,g in sorted(odds.items(),key=lambda kv:kv[1]['commence']):
    tc=datetime.fromisoformat(g['commence'].replace('Z','+00:00'));best=None
    for i,t,A,H in esp:
        if i in used or abs((t-tc).total_seconds())>3*3600: continue
        for s,fl in ((TC.sim(g['away'],A)+TC.sim(g['home'],H),False),(TC.sim(g['away'],H)+TC.sim(g['home'],A),True)):
            if best is None or s>best[0]: best=(s,i,fl,A,H)
    if best and best[0]>=1.2: used.add(best[1]); M[(best[3]['abbreviation'],best[4]['abbreviation'])]=(g,best[2])
V=dict(l.split() for l in open(VER))
imp=lambda p:(100/(p+100)) if p>0 else (-p/(-p+100))
def wu(p): return p/100 if p>0 else 100/-p
G=json.load(open(GO))['updates'];out=[];nclv=0
for u in G:
    d=json.load(open(f"{PEND}/{u['id']}.json"));a,h=d['away'],d['home']
    m=M.get((a,h)); fl=False
    if not m and (h,a) in M: m=M[(h,a)]; fl=True
    w=dict(op='update',collection='sports/ncaam/picks',doc_id=u['id'],if_version=int(V[u['id']]),data=dict(result=u['result'],final=u['final']))
    pr=d.get('price') or -110
    w['data']['units']=round(wu(pr),3) if u['result']=='win' else (-1 if u['result']=='loss' else 0)
    if m:
        g,f0=m; flip=f0^fl; c=g.get('close') or g.get('now') or {}; csrc='The Odds API median close' if g.get('close') else 'The Odds API last pre-tip read (no close tick saved)'
        mk=d['market']; ln=d.get('line')
        try:
          if mk=='Total' and c.get('total') is not None and ln is not None:
            side='Under' if d['pick'].startswith('Under') else 'Over'
            w['data'].update(close_line=c['total'],close_price=c.get('under_price' if side=='Under' else 'over_price'),clv=round((ln-c['total']) if side=='Under' else (c['total']-ln),1))
          elif mk=='Spread' and c.get('spread_home') is not None and ln is not None:
            sh=-c['spread_home'] if flip else c['spread_home']
            home=d['pick'].split()[0]==h
            cl=sh if home else -sh
            ph=c.get('spread_away_price' if flip else 'spread_home_price'); pa=c.get('spread_home_price' if flip else 'spread_away_price')
            w['data'].update(close_line=cl,close_price=ph if home else pa,clv=round(ln-cl,1))
          elif mk=='Moneyline':
            team=d['pick'].split()[0]; mh,ma=(c.get('ml_away'),c.get('ml_home')) if flip else (c.get('ml_home'),c.get('ml_away'))
            cp=mh if team==h else ma
            if cp: w['data'].update(close_price=int(cp),clv=round(100*(imp(cp)-imp(pr)),1))
          if 'clv' in w['data']: w['data']['close_source']=csrc; nclv+=1
        except Exception as ex: print('err',u['id'],ex)
    out.append(w)
json.dump(out,open(OUT,'w'))
print('writes',len(out),'clv',nclv)
