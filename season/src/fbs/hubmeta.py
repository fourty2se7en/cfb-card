import json, glob, re
from pathlib import Path
import pandas as pd, numpy as np
import rules as RU
D=Path('.'); X=Path('/home/claude/cfb/x'); HUB=Path('/home/claude/cfb/hub')
W=json.load(open(X/'writes.json'))
SIG=json.load(open('signals.json'))
def L(div):
    out=[]
    for f in glob.glob(str(HUB/'sports'/div/'picks'/'*.json')):
        d=json.load(open(f)); out.append(d.get('data',d))
    return out
def pay(r,p): return RU.payout(True if r=='win' else (False if r=='loss' else None), p or -110)
def rec(rows):
    w=sum(r['result']=='win' for r in rows); l=sum(r['result']=='loss' for r in rows); p=sum(r['result']=='push' for r in rows)
    return dict(w=w,l=l,p=p,u=round(sum(pay(r['result'],r.get('price')) for r in rows),2))
watch={}; close={}
for div in ('fbs','fcs'):
    m=json.load(open(HUB/'meta'/f'{div}.json')); m=m.get('data',m)
    RE=json.load(open(f'ruleeval_{div}.json')); RS=SIG['rules_'+div]
    l3=[p for p in RE['periods'] if p.startswith('Last 3')][0]
    new=[]; watch[div]=[]; close[div]=[]
    for r in m['rules']:
        if r['market']=='Prop': continue
        k=r['key']; R_=RS['total'][k] if k in RS['total'] else RS['side'][k]
        v=RE['rules'][k]['versions'][0]['rec']; s=v['Season']; mo=v.get('Nov')
        r=dict(r); r['on']=R_['on']; r['tier']=R_['tier']
        r['season']=dict(w=s['w'],l=s['l'],p=s['p'],u=s['units'])
        r['month']=dict(w=mo['w'],l=mo['l'],p=mo['p'],u=mo['units'],label='Nov') if mo else dict(w=0,l=0,p=0,u=0.0,label='Nov')
        r['every_game']=f"{s['w']}-{s['l']} {s['units']:+.1f}u"; L3=v[l3]; r['last_3_weeks']=f"{L3['w']}-{L3['l']} {L3['units']:+.1f}u" if L3['n'] else None
        r['version']=R_.get('version',r.get('version'))
        if R_.get('switched'): r['switched']=R_['switched']
        r['back_on']='Back on when season and month (5+ picks) are both green.'
        mm=r['month']; mn=mm['w']+mm['l']
        if r['on']:
            if (s['n']>=20 and s['units']<1) or (mm['u']<1 and mn>=4 and s['n']>=20): watch[div].append(f"{r['label']}: Nov {mm['w']}-{mm['l']} {mm['u']:+.1f}u on {mn} picks, a loss on the 5th November pick turns it off" if mn<5 else f"{r['label']}: Nov {mm['u']:+.1f}u")
        new.append(r)
    if div=='fbs':
        rows=[x for x in L(div) if x['market']=='Prop' and x['result'] in ('win','loss','push')]
        cats=sorted({(x['stat'],x['side']) for x in rows})
        for st,sd in cats:
            rr=[x for x in rows if x['stat']==st and x['side']==sd]; s=rec(rr); mo=rec([x for x in rr if x['date']>='2026-11-01'])
            n=s['w']+s['l']; mn=mo['w']+mo['l']
            on=not (n>=20 and (s['u']<0 or (mn>=5 and mo['u']<0)))
            e=dict(key=f"PROP_{re.sub('[^a-z]','',st)}_{sd}",keys=[],label=f"{st.capitalize()} · {sd}",market='Prop',desc=f"Every logged {st} {sd.lower()} prop (Play and tracking) in the hub ledger.",
                   on=on,season=s,month=dict(mo,label='Nov'),every_game=None,card=f"{s['w']}-{s['l']}"+(f"-{s['p']}" if s['p'] else '')+f" {s['u']:+.2f}u",
                   back_on='Back on when season and month (5+ picks) are both green.')
            if on and s['u']<1 and n>=17: watch[div].append(f"{e['label']} props: season {s['w']}-{s['l']}-{s['p']} {s['u']:+.2f}u on {n} graded picks; turns off at 20 picks if still negative")
            new.append(e)
    m['rules']=new; m['updated']='2026-11-06'
    m['policy']=dict(m['policy'],off_min=20,month_min=5,on_min=0,freeze_until=None)
    m['notes']=(f"Rule evaluation Nov 6: {RE['games']} {div.upper()} games graded (weeks {RE['weeks'][0]} to {RE['weeks'][1]}), November graded for the first time. No switches. "
                +("Watch: "+'; '.join(watch[div])+'.' if watch[div] else 'No warnings.')+(" Player props: Play or tracking (leans are tracking only)." if div=='fbs' else ''))
    m['prop_lean_tracking']=True if div=='fbs' else m.get('prop_lean_tracking',False)
    W[f'meta|{div}']=m
# ---------- standings ----------
R=Path('repo'); PR=pd.read_csv(R/'power_ratings.csv').set_index('team')
GM=pd.read_csv(R/'games.csv'); GM=GM[(GM.season==2026)&GM.homePoints.notna()]
TM=pd.read_csv(R/'teams.csv'); TM['_k']=TM.classification.map({'fbs':0,'fcs':1}).fillna(2); TM=TM.sort_values('_k').drop_duplicates('school').set_index('school')
P4={'ACC','Big 12','Big Ten','SEC'}
def team_rec(t):
    h=GM[GM.homeTeam==t]; a=GM[GM.awayTeam==t]
    w=int((h.homePoints>h.awayPoints).sum()+(a.awayPoints>a.homePoints).sum()); l=int(len(h)+len(a)-w)
    ch=h[h.conferenceGame.astype(bool)]; ca=a[a.conferenceGame.astype(bool)]
    cw=int((ch.homePoints>ch.awayPoints).sum()+(ca.awayPoints>ca.homePoints).sum()); cl=int(len(ch)+len(ca)-cw)
    return w,l,cw,cl
for div in ('fbs','fcs'):
    S=json.load(open(f'slate_{div}.json')); old=json.load(open(HUB/'standings'/f'{div}.json')); old=old.get('data',old)
    CT=S['conf']; rows=[]
    for c,d in sorted(CT.items(),key=lambda kv:-kv[1]['rating']):
        vs=lambda k:'%d-%d'%tuple(d['vs'].get(k,[0,0]))
        rows.append(dict(team=c,values={'Tier':'Power 4' if c in P4 else ('FCS' if c=='FCS' else 'Group of 5'),'Rating':f"{d['rating']:+.1f}",'Non-conf W-L':f"{d['w']}-{d['l']}",'Avg margin':f"{d['pf']/max(d['n'],1):+.1f}",'vs Power 4':vs('Power 4'),'vs Group of 5':vs('Group of 5'),'vs FCS':vs('FCS')}))
    g0=dict(old['groups'][0]); g0['rows']=rows
    p4=[CT[c] for c in CT if c in P4]; p4g5=(sum(d['vs'].get('Group of 5',[0,0])[0] for d in p4),sum(d['vs'].get('Group of 5',[0,0])[1] for d in p4))
    g0['note']=re.sub(r'\d+ so far',f"{S['nconf']} so far",g0['note']); g0['note']=re.sub(r'Power 4 is \d+-\d+',f'Power 4 is {p4g5[0]}-{p4g5[1]}',g0['note'])
    groups=[g0]
    pr=PR[PR.division==div]
    for c,sub in sorted(pr.groupby('conference'),key=lambda kv:-kv[1].rating.mean()):
        recs={t:team_rec(t) for t in sub.index}
        order=sorted(sub.index,key=lambda t:(-(recs[t][2]/max(recs[t][2]+recs[t][3],1)),-recs[t][2],-sub.rating[t]))
        rr=[]
        for t in order:
            w,l,cw,cl=recs[t]; col=TM.color[t] if t in TM.index and isinstance(TM.color[t],str) else None
            rr.append(dict(team=t,code=re.sub('[^A-Za-z0-9]','',t),mascot=(TM.mascot[t] if t in TM.index and isinstance(TM.mascot[t],str) else None),color=col,
                           values={'Rank':int(sub['rank'][t]) if sub['rank'][t]==sub['rank'][t] else None,'Conf':f'{cw}-{cl}','Overall':f'{w}-{l}','Rating':f"{sub.rating[t]:+.1f}",'Talent prior':f"{sub.talent_prior[t]:+.1f}",'Form':f"{sub.form[t]:+.1f}"}))
        groups.append(dict(name=c,kind='conference',columns=['Rank','Conf','Overall','Rating','Talent prior','Form'],rows=rr))
    W[f'standings|{div}']=dict(sport=div,updated='2026-11-06',week=S['week'],title_label=None,note=old.get('note'),groups=groups)
json.dump(W,open(X/'writes.json','w'),default=str)
print(json.dumps(watch,indent=0)); print(json.dumps(W['meta|fbs']['rules'][-3:],indent=0)[:1200])
