import json, re
from pathlib import Path
import pandas as pd
W={}
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
for div in ('fbs',):
    S=json.load(open(f'slate_{div}.json')); old=json.load(open(Path('stdl')/'standings'/f'{div}.json')); old=old.get('data',old)
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
    W[f'standings|{div}']=dict(sport=div,updated='2026-11-12',week=S['week'],title_label=None,note=old.get('note'),groups=groups)

for k,v in W.items():
    json.dump(v,open('x/'+k.replace('|','_')+'.json','w'),default=str)
print(list(W))
