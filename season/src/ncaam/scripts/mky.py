import sys,json,gzip
from datetime import datetime
sys.path[:0]=['/home/claude/season/ncaam/repo/odds','/home/claude/season/ncaam/repo/season']
import read as R, t222_college as TC
DAY=sys.argv[1]; OUT=sys.argv[2]
D=f'/home/claude/season/ncaam/repo/season/data/espn/ncaam/{DAY}'
ev=json.load(gzip.open(D+'/scoreboard_final.json.gz'))['events']; BX=json.load(gzip.open(D+'/boxscores.json.gz'))
odds=R.build('ncaam',DAY); M={};used=set()
esp=[(e['id'],datetime.fromisoformat(e['date'].replace('Z','+00:00')),*[ {x['homeAway']:x['team'] for x in e['competitions'][0]['competitors']}[k] for k in ('away','home')]) for e in ev]
for k,g in sorted(odds.items(),key=lambda kv:kv[1]['commence']):
    tc=datetime.fromisoformat(g['commence'].replace('Z','+00:00'));best=None
    for i,t,A,H in esp:
        if i in used or abs((t-tc).total_seconds())>3*3600: continue
        for s,fl in ((TC.sim(g['away'],A)+TC.sim(g['home'],H),False),(TC.sim(g['away'],H)+TC.sim(g['home'],A),True)):
            if best is None or s>best[0]: best=(s,i,fl)
    if best and best[0]>=1.2: used.add(best[1]); M[best[1]]=(g,best[2])
z=lambda v:'' if v is None else (f'{v:g}' if isinstance(v,float) else str(v))
rows=[];nc=0
for e in ev:
    if not e['status']['type'].get('completed'): continue
    c=e['competitions'][0]; C={x['homeAway']:x for x in c['competitors']}; h,a=C['home'],C['away']
    if not h['team'].get('conferenceId') or not a['team'].get('conferenceId'): continue
    rk=lambda x:'' if (x.get('curatedRank') or {}).get('current',99) in (99,None) else str(x['curatedRank']['current'])
    l1=lambda x:str(int(x['linescores'][0]['value'])) if x.get('linescores') else ''
    bx='';b=BX.get(e['id'])
    if b:
        S={}
        for t in b['teams']:
            ab=t['team']['abbreviation'];st={q['name']:q['displayValue'] for q in t['statistics']}
            fg=st.get('fieldGoalsMade-fieldGoalsAttempted');ft=st.get('freeThrowsMade-freeThrowsAttempted')
            S[ab]=[fg.split('-')[1] if fg else '',st.get('offensiveRebounds',''),st.get('totalTurnovers') or st.get('turnovers',''),ft.split('-')[1] if ft else '']
        if h['team']['abbreviation'] in S and a['team']['abbreviation'] in S: bx=','.join(S[h['team']['abbreviation']]+S[a['team']['abbreviation']])
    od=''
    if e['id'] in M:
        g,fl=M[e['id']];o=g.get('open') or {};cl=g.get('close') or g.get('now') or {}
        if cl.get('spread_home') is not None:
            sg=-1 if fl else 1
            mh,ma=(cl.get('ml_away'),cl.get('ml_home')) if fl else (cl.get('ml_home'),cl.get('ml_away'))
            od=','.join(z(v) for v in [sg*o['spread_home'] if o.get('spread_home') is not None else None, sg*cl['spread_home'], o.get('total'), cl.get('total'), mh, ma]); nc+=1
    if not od and c.get('odds'):
        x=c['odds'][0]; od=','.join(z(v) for v in [None,x.get('spread'),None,x.get('overUnder'),(x.get('homeTeamOdds') or {}).get('moneyLine'),(x.get('awayTeamOdds') or {}).get('moneyLine')])
    vs=(c.get('venue') or {}).get('address',{}).get('state','')
    rows.append('|'.join(['M',e['id'],h['team']['abbreviation'],a['team']['abbreviation'],str(h['team']['conferenceId']),str(a['team']['conferenceId']),'1' if c.get('conferenceCompetition') else '0','1' if c.get('neutralSite') else '0',rk(h),rk(a),str(h['score']),str(a['score']),l1(h),l1(a),vs,bx,od]))
open(OUT,'w').write('\n'.join(rows)+'\n'); print('rows',len(rows),'odds api close',nc,'no odds',sum(1 for r in rows if r.endswith('|')))
