import json
from harness import *
import tests2 as T2
S={s:json.load(open(s+'.json')) for s in ['nba','nhl','nfl','fbs','ncaam']}
def half(rows):
  ds=sorted(r['date'] for r in rows);m=ds[len(ds)//2];return lambda r:'1st half' if r['date']<m else '2nd half'
def show(t,R,keep):print('  '+t.ljust(36),' | '.join(f"{k[1]}: {v}" for k,v in sorted(R.items(),key=lambda kv:str(kv[0])) if k[0]==keep))
n=S['nba'];show('NBA model at opener, Spread',run(T2.at_open(n),split=half(n)),'Spread')
show('NBA blend50+calibrated, Total',run(n,'blend',0.5,calibrate=True,split=half(n)),'Total')
show('NBA calibrated, Total',run(n,calibrate=True,split=half(n)),'Total')
show('NBA line moved our way, Total',run(n,need_move=True,split=half(n)),'Total')
c=S['ncaam'];show('NCAAM calibrated, Spread',run(c,calibrate=True,split=half(c)),'Spread')
f=S['nfl'];show('NFL model at opener, Spread',run(T2.at_open(f),split=half(f)),'Spread')
show('NFL line moved our way, Spread',run(f,need_move=True,split=half(f)),'Spread')
show('NFL line moved our way, Total',run(f,need_move=True,split=half(f)),'Total')
h=S['nhl'];show('NHL line moved our way, Total',run(h,need_move=True,split=half(h)),'Total')
b=S['fbs'];show('FBS blend50 + moved our way',run(b,'blend',0.5,need_move=True,split=half(b)),'Spread')
