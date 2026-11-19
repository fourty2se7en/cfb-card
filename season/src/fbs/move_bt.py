import gzip,json,math,numpy as np,pandas as pd,sys
rows=[]
for y in range(2017,2026):
    games={g['id']:g for g in json.load(gzip.open(f'bt/games_{y}.json.gz'))}
    for l in json.load(gzip.open(f'bt/lines_{y}.json.gz')):
        g=games.get(l['id'])
        if not g or l.get('homeClassification')!='fbs' or l.get('awayClassification')!='fbs' or g.get('seasonType')!='regular': continue
        if g.get('homePoints') is None: continue
        L=l.get('lines') or []
        sp=[x['spread'] for x in L if x.get('spread') is not None]; so=[x['spreadOpen'] for x in L if x.get('spreadOpen') is not None]
        tt=[x['overUnder'] for x in L if x.get('overUnder')]; to=[x['overUnderOpen'] for x in L if x.get('overUnderOpen')]
        rows.append(dict(season=y,margin=g['homePoints']-g['awayPoints'],pts=g['homePoints']+g['awayPoints'],
          sp=np.median(sp) if sp else None, so=np.median(so) if so else None, tt=np.median(tt) if tt else None, to=np.median(to) if to else None, n_open=len(so)))
T=pd.DataFrame(rows); print(len(T),'games; with spread opener',T.so.notna().sum(),'total opener',T.to.notna().sum())
print(T[T.so.notna()].groupby('season').size().to_dict())
def rep(name,side,res,mask):
    for lab,f in (('train',T.season<=2022),('test',T.season>=2023),('all',T.season>0)):
        m=mask&(side!=0)&f; c=(res[m]*side[m]); c=c[c!=0]; n=len(c)
        if n==0: print(f'{name:48s} {lab}: n=0'); continue
        p=(c>0).mean(); se=math.sqrt(p*(1-p)/n); print(f'{name:48s} {lab:5s} n={n:5d} hit={p:.3f} ({p-1.96*se:.3f},{p+1.96*se:.3f})')
cover=np.sign(T.margin+T.sp)  # +1 home covers close
ok=T.so.notna()&T.sp.notna()
mv=(T.sp-T.so)   # negative: home became bigger favourite -> moved toward home
for t in (0.5,1.0,1.5,2.5):
    side=np.where(mv<=-t,1,np.where(mv>=t,-1,0)); rep(f'Follow spread move {t}+ (vs close)',side,cover,ok)
    rep(f'Fade spread move {t}+ (vs close)',-side,cover,ok)
okt=T.to.notna()&T.tt.notna(); ores=np.sign(T.pts-T.tt); tm=T.tt-T.to
for t in (1.0,1.5,2.5):
    rep(f'Total moved down {t}+: under (vs close)',np.where(tm<=-t,-1,0),ores,okt)
    rep(f'Total moved up {t}+: over (vs close)',np.where(tm>=t,1,0),ores,okt)
# vs the opener (what you'd get betting early with the move)
cover_o=np.sign(T.margin+T.so); 
for t in (1.0,2.5):
    side=np.where(mv<=-t,1,np.where(mv>=t,-1,0)); rep(f'Follow spread move {t}+ (bet at OPEN)',side,cover_o,ok)
