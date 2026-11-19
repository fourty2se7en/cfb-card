import json
from harness import *
import tests3 as T3
S={s:json.load(open(s+'.json')) for s in ['nba','nhl','nfl','fbs','ncaam']}
def d(R):return dict(w=R.w,l=R.l,p=R.p,u=round(R.u,2))
out={}
out['nba/NBA_TOT_CAL']=d(run(S['nba'],'blend',0.5,calibrate=True)['Total'])
out['nba/NBA_TOT_MOVE']=d(run(S['nba'],need_move=True)['Total'])
out['ncaam/NCAAM_SP_CAL']=d(run(S['ncaam'],calibrate=True)['Spread'])
nhl=sorted(S['nhl'],key=lambda r:r['date'])
out['nhl/NHL_REST_ML']=d(T3.spot(nhl,T3.b2b,T3.rested,'ML'))
out['nfl/NFL_REST_SP']=d(T3.spot(S['nfl'],T3.ra,lambda r:'H' if r['restH']>r['restA'] else 'A','Spread'))
out['nfl/NFL_DIV_DOG']=d(T3.spot(S['nfl'],lambda r:r.get('div')==1 and good(r.get('sp_close_h')) and r['sp_close_h']!=0,lambda r:'H' if r['sp_close_h']>0 else 'A','Spread'))
out['nhl/NHL_BACKUP_G_ML']=d(T3.spot(nhl,T3.bk,lambda r:'A' if r['backupA'] else 'H','ML'))
for sp in S:
  for mk,R in run(S[sp]).items():out[f'{sp}/MODEL_ONLY_{mk.upper().replace(" ","_")}']=d(R)
json.dump(out,open('newrules.json','w'),indent=0);print(json.dumps(out))
