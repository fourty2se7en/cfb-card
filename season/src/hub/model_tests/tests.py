import json,sys,collections
from harness import *
S={s:json.load(open(s+'.json')) for s in ['nba','nhl','nfl','fbs','ncaam']}
def show(title,R):
  print('  '+title.ljust(28),' | '.join(f"{k}: {v}" for k,v in sorted(R.items(),key=lambda kv:str(kv[0]))))
for sp,rows in S.items():
  print('=====',sp,len(rows),'games',rows[0]['date'] if rows else '', 'to', max(r['date'] for r in rows))
  show('0 raw model (1% edge)',run(rows))
  show('1 blend 50/50 with opener',run(rows,'blend',0.5))
  show('1 blend 25 model/75 opener',run(rows,'blend',0.25))
  show('2 calibrated raw',run(rows,calibrate=True))
  show('1+2 blend 50 + calibrated',run(rows,'blend',0.5,calibrate=True))
  show('4 raw, line moved our way',run(rows,need_move=True))
  show('4 blend50, line moved our way',run(rows,'blend',0.5,need_move=True))
