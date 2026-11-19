import json,gzip,collections,sys
R='/home/claude/season/ncaam/repo/season/data/espn/ncaam/'; DS=sys.argv[1]; OUT=f'/home/claude/season/ncaam/w/data/raw/lineups_m_{DS}.txt'
G=collections.defaultdict(list)
import os
for d in sorted(os.listdir(R)):
    try: b=json.load(gzip.open(R+d+'/boxscores.json.gz'))
    except Exception: continue
    for gid,x in b.items():
        for t in x.get('players') or []:
            ab=t['team']['abbreviation']; st=t['statistics'][0]; k=st['keys']
            rows=[]
            for a in st.get('athletes',[]):
                s=a.get('stats') or []
                if not s or len(s)<len(k): continue
                v=dict(zip(k,s))
                try: mn=float(v['minutes'] or 0)
                except: mn=0
                if mn<=0: continue
                ath=a['athlete'];rows.append((ath.get('shortName') or ath.get('displayName'),(ath.get('position') or {}).get('abbreviation',''),bool(a.get('starter')),mn,float(v.get('points') or 0),float(v.get('rebounds') or 0),float(v.get('assists') or 0)))
            G[ab].append((d,rows))
pr=[]; lu=[]
for ab,gl in G.items():
    gl=sorted(gl)[-3:]; agg=collections.defaultdict(lambda:[0,0,0,0,0,'',0])
    for d,rows in gl:
        for n,p,s,m,pt,rb,asst in rows:
            a=agg[n];a[0]+=1;a[1]+=m;a[2]+=pt;a[3]+=rb;a[4]+=asst;a[5]=p;a[6]+=s
    last=gl[-1][1]; starters=[r[0] for r in last if r[2]][:5]
    def f(n,b):
        a=agg[n];g=a[0];return f"{n},{a[5]},{'b' if b else ''},{a[1]/g:.0f},{a[2]/g:.1f},{a[3]/g:.1f},{a[4]/g:.1f}"
    bench=sorted([n for n in agg if n not in starters],key=lambda n:-agg[n][1]/agg[n][0])[:1]
    lu.append(f"{ab}|{len(gl)}|"+';'.join([f(n,False) for n in starters]+[f(n,True) for n in bench]))
open(OUT,'w').write('0|50|50\n@@LU\n'+'\n'.join(lu)+'\n'); print('teams',len(lu))
