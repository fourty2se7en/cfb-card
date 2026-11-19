import json
from harness import *
S={s:json.load(open(s+'.json')) for s in ['nba','nhl','nfl','fbs']}
def show(t,R):print('  '+t.ljust(34),' | '.join(f"{k}: {v}" for k,v in sorted(R.items(),key=lambda kv:str(kv[0]))))
print('== 5 sport fixes')
# NHL totals: walk-forward goal scaling
nhl=sorted(S['nhl'],key=lambda r:r['date']);fac={}
for r in nhl:
  P=[x for x in nhl if x['date']<r['date']]
  fac[(r['date'],r['a'])]=(sum(x['as_']+x['hs'] for x in P)/sum(x['lamT'] for x in P)) if len(P)>=30 else 1.0
show('NHL totals, scoring rate rescaled',{k:v for k,v in run(nhl,tscale_fn=lambda r:fac[(r['date'],r['a'])]).items() if k=='Total'})
show('NHL totals, raw (compare)',{k:v for k,v in run(nhl).items() if k=='Total'})
show('NFL moneyline, -200 to +200 only',{k:v for k,v in run(S['nfl'],price_lim=(-200,200)).items() if k=='Moneyline'})
show('NBA moneyline, -200 to +200 only',{k:v for k,v in run(S['nba'],price_lim=(-200,200)).items() if k=='Moneyline'})
show('NHL moneyline, -200 to +200 only',{k:v for k,v in run(nhl,price_lim=(-200,200)).items() if k=='Moneyline'})
show('FBS moneyline, -200 to +200 only',{k:v for k,v in run(S['fbs'],price_lim=(-200,200)).items() if k=='Moneyline'})
show('NHL model ML: dogs only',{k:v for k,v in run(nhl,price_lim=(100,250)).items() if k=='Moneyline'})
show('NBA model ML: dogs only',{k:v for k,v in run(S['nba'],price_lim=(100,400)).items() if k=='Moneyline'})
print('== 6 situational spots (no model), at the close')
def spot(rows,cond,side_fn,mk):
  R=Rec()
  for r in rows:
    if not cond(r):continue
    s=side_fn(r);a,h=r['as_'],r['hs']
    if mk=='Spread':
      if not good(r.get('sp_close_h')):continue
      o=(h-a)+r['sp_close_h'];win=None if o==0 else ((o>0)==(s=='H'));pr=(r.get('sp_ph') if s=='H' else r.get('sp_pa')) or -110
    elif mk=='Puck line':
      if not good(r.get('pl_ph')):continue
      o=(h-a)-r['pl_sp_a'];win=None if o==0 else ((o>0)==(s=='H'));pr=r['pl_ph'] if s=='H' else r['pl_pa']
    elif mk=='ML':
      if not good(r.get('ml_h')):continue
      win=None if a==h else ((h>a)==(s=='H'));pr=r['ml_h'] if s=='H' else r['ml_a']
    elif mk=='Under':
      if not good(r.get('tot_close')):continue
      T=a+h;L=r['tot_close'];win=None if T==L else T<L;pr=r.get('pu') or -110
    R.add(win,pr)
  return R
b2b=lambda r:good(r.get('restA')) and good(r.get('restH')) and ((r['restA']==0)!=(r['restH']==0))
rested=lambda r:'H' if r['restA']==0 else 'A'
for mk in ['Spread','ML']:print('  NBA back to back: back the rested team',mk,spot(S['nba'],b2b,rested,mk))
for mk in ['Puck line','ML']:print('  NHL back to back: back the rested team',mk,spot(nhl,b2b,rested,mk))
ra=lambda r:good(r.get('restA')) and good(r.get('restH')) and abs(r['restA']-r['restH'])>=3
print('  NFL rest edge 3+ days: back the rested team Spread',spot(S['nfl'],ra,lambda r:'H' if r['restH']>r['restA'] else 'A','Spread'))
print('  NFL wind 15+ mph, outdoors: Under',spot(S['nfl'],lambda r:good(r.get('wind')) and r['wind']>=15 and r.get('roof')=='outdoors',None,'Under'))
print('  NFL division game: back the underdog Spread',spot(S['nfl'],lambda r:r.get('div')==1 and good(r.get('sp_close_h')) and r['sp_close_h']!=0,lambda r:'H' if r['sp_close_h']>0 else 'A','Spread'))
print('== 3 lineups (NHL goalie, the only saved history)')
bk=lambda r:r.get('backupA') is not None and r.get('backupH') is not None and r['backupA']!=r['backupH'] and r['date']>='2026-10-15'
starter=lambda r:'H' if r['backupA'] else 'A'
for mk in ['ML','Puck line']:print('  NHL backup goalie: back the team with its No. 1',mk,spot(nhl,bk,starter,mk))
