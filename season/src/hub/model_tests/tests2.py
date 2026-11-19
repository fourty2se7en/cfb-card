import json,copy
from harness import *
S={s:json.load(open(s+'.json')) for s in ['nba','nhl','nfl','fbs']}
def at_open(rows):
  out=[]
  for r in rows:
    r=copy.deepcopy(r)
    if r['sport']=='nhl':
      if good(r.get('pl_open_ph')):r['pl_ph'],r['pl_pa']=r['pl_open_ph'],r['pl_open_pa']
      else:r['p_pl_h']=None
      if good(r.get('tot_open')) and good(r.get('po_open')):
        r['tot_close'],r['po'],r['pu']=r['tot_open'],r['po_open'],r['pu_open']
      else:r['tot_close']=None
    else:
      if good(r.get('sp_open_h')):r['sp_close_h']=r['sp_open_h'];r['sp_ph']=r['sp_pa']=-110
      else:r['hm']=None
      if good(r.get('tot_open')):r['tot_close']=r['tot_open'];r['po']=r['pu']=-110
      else:r['tot_m']=None
    if good(r.get('ml_open_h')):r['ml_h'],r['ml_a']=r['ml_open_h'],r['ml_open_a']
    else:r['ml_h']=None
    out.append(r)
  return out
def show(t,R):print('  '+t.ljust(30),' | '.join(f"{k}: {v}" for k,v in sorted(R.items(),key=lambda kv:str(kv[0]))))
def clv(rows):
  # among raw bets at open, share where close moved toward the bet
  C=collections.defaultdict(lambda:[0,0])
  ro={(r['date'],r['a'],r['h']):r for r in rows}
  for r in rows:
    o=at_open([r])[0]
    for mk,p,pA,pB,oA,mv in markets(o,'raw'):
      s=bet(p,pA,pB)
      if s is None:continue
      for mk2,_,_,_,_,mv2 in markets(r,'raw'):
        if mk2==mk and mv2 is not None and mv2!=0:C[mk][0 if (mv2>0)==(s=='A') else 1]+=1
  return {k:f"{a}/{a+b} moved our way ({100*a/(a+b):.0f}%)" for k,(a,b) in C.items()}
for sp,rows in S.items():
  O=at_open(rows);print('=====',sp)
  show('0 raw at opening line',run(O))
  show('1 half-strength model at open',run(O,'blend',0.5)) if False else None
  show('2 calibrated at open',run(O,calibrate=True))
  print('   CLV:',clv(rows))
