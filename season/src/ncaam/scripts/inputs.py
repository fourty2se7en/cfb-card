import sys,json,gzip
from datetime import datetime,timedelta,timezone
sys.path[:0]=['/home/claude/season/ncaam/repo/odds','/home/claude/season/ncaam/repo/season']
import read as R, t222_college as TC
import sys
DAY=sys.argv[1];DS=DAY.replace('-','');W='/home/claude/season/ncaam/w/data'
PHX=timezone(timedelta(hours=-7))
ev=json.load(gzip.open(f'/home/claude/season/ncaam/repo/season/data/espn/ncaam/{DAY}/scoreboard.json.gz'))['events']
# teaminfo
ti=[]
for e in ev:
    c=e['competitions'][0];C={x['homeAway']:x for x in c['competitors']}
    def t(x):
        r={q.get('type'):q.get('summary') for q in x.get('records',[])}
        return f"{x['team'].get('displayName')}^{x['team'].get('color') or ''}^{r.get('total','')}/{r.get('home','')}/{r.get('road','')}"
    v=c.get('venue') or {};ad=v.get('address') or {}
    ti.append('|'.join([e['id'],t(C['away']),t(C['home']),f"{v.get('fullName','')}, {ad.get('city','')} {ad.get('state','')}"]))
open(f'{W}/raw/teaminfo_m_{DS}.txt','w').write('\n'.join(ti)+'\n')
# 1H lines (Odds API periods_now h1, else periods_close)
odds=R.build('ncaam',DAY);esp=[(e['id'],datetime.fromisoformat(e['date'].replace('Z','+00:00')),*[{x['homeAway']:x['team'] for x in e['competitions'][0]['competitors']}[k] for k in ('away','home')]) for e in ev]
used=set();M={}
for k,g in sorted(odds.items(),key=lambda kv:kv[1]['commence']):
    tc=datetime.fromisoformat(g['commence'].replace('Z','+00:00'));best=None
    for i,tt,A,H in esp:
        if i in used or abs((tt-tc).total_seconds())>3*3600: continue
        for s,fl in ((TC.sim(g['away'],A)+TC.sim(g['home'],H),False),(TC.sim(g['away'],H)+TC.sim(g['home'],A),True)):
            if best is None or s>best[0]: best=(s,i,fl,A,H)
    if best and best[0]>=1.2: used.add(best[1]); M[best[1]]=(g,best[2],best[3],best[4])
out=[];n=0;rawh={}
f=lambda v:'PK' if v==0 else f"{v:+g}"
for i,(g,fl,A,H) in M.items():
    h1=(g.get('periods_now') or {}).get('h1') or (g.get('periods_close') or {}).get('h1')
    if not h1 or h1.get('spread_home') is None or h1.get('total') is None: continue
    sh=-h1['spread_home'] if fl else h1['spread_home']
    ph,pa=(h1.get('spread_away_price'),h1.get('spread_home_price')) if fl else (h1.get('spread_home_price'),h1.get('spread_away_price'))
    tm=datetime.fromisoformat(g['commence'].replace('Z','+00:00')).astimezone(PHX).strftime('%I:%M %p').lstrip('0')
    out.append(f"H|{tm}|{A['abbreviation']}|{f(-sh)}{int(pa or -110):+d}|o{h1['total']:g}{int(h1.get('over_price') or -110):+d}|")
    out.append(f"H|{tm}|{H['abbreviation']}|{f(sh)}{int(ph or -110):+d}|u{h1['total']:g}{int(h1.get('under_price') or -110):+d}|"); n+=1
    rawh[i]=h1
open(f'{W}/raw/t222_m1h_{DS}.txt','w').write('\n'.join(out)+'\n')
json.dump({k:v for k,v in odds.items()},open(f'{W}/raw/odds_ncaam_{DS}.json','w'))
print('teaminfo',len(ti),'1H games',n)
