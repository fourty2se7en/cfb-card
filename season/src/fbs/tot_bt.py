import gzip,json,math,numpy as np,pandas as pd
rows=[]
for y in range(2016,2026):
    for g in json.load(gzip.open(f'bt/games_{y}.json.gz')):
        if g.get('seasonType')!='regular' or g.get('homePoints') is None: continue
        rows.append(dict(id=g['id'],season=y,week=g['week'],home=g['homeTeam'],away=g['awayTeam'],hc=g['homeClassification'],ac=g['awayClassification'],pts=g['homePoints']+g['awayPoints'],hp=g['homePoints'],ap=g['awayPoints'],conf=bool(g.get('conferenceGame'))))
G=pd.DataFrame(rows)
OU={}
for y in range(2017,2026):
    for l in json.load(gzip.open(f'bt/lines_{y}.json.gz')):
        s=[x['overUnder'] for x in (l.get('lines') or []) if x.get('overUnder')]
        if s: OU[l['id']]=float(np.median(s))
G['ou']=G.id.map(OU)
out=[]
for (y,w),S in G[G.season>=2017].groupby(['season','week']):
    P=G[(G.season==y)&(G.week<w)]
    tm={}
    for r in P.itertuples():
        tm.setdefault(r.home,[]).append((r.week,r.pts)); tm.setdefault(r.away,[]).append((r.week,r.pts))
    for r in S[(S.hc=='fbs')&(S.ac=='fbs')&S.ou.notna()].itertuples():
        a=sorted(tm.get(r.home,[]))[-3:]; b=sorted(tm.get(r.away,[]))[-3:]
        if len(a)<3 or len(b)<3: continue
        rec=(np.mean([x[1] for x in a])+np.mean([x[1] for x in b]))/2
        out.append(dict(season=y,ou=r.ou,pts=r.pts,rec=rec,conf=r.conf))
T=pd.DataFrame(out); T['res']=np.sign(T.pts-T.ou)
def rep(name,side):
    for lab,f in (('train',T.season<=2022),('test',T.season>=2023),('all',T.season>0)):
        m=(side!=0)&f; c=(T.res[m]*side[m]); c=c[c!=0]; p=(c>0).mean(); n=len(c); se=math.sqrt(p*(1-p)/n)
        print(f'{name:45s} {lab:5s} n={n:5d} hit={p:.3f} ci=({p-1.96*se:.3f},{p+1.96*se:.3f})')
for t in (4,7,10):
    d=T.rec-T.ou; rep(f'Recent scoring (last 3) {t}+ off total',np.where(d>=t,1,np.where(d<=-t,-1,0)))
rep('Conference game: under',np.where(T.conf,-1,0))
rep('Every game: under',np.full(len(T),-1))
