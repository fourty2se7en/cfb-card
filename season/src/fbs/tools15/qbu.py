"""QB usage from repo ESPN box scores (Nov 15): per team season attempts by passer, QB1, share, last game passer,
and for a team whose last game passer differs from QB1: that passer's starts (most attempts in a game), record and stats."""
import json,gzip,glob,os,collections,sys
B='/home/claude/cfb15_fbs/season/data/espn/fbs'
TM={} ; games=[]
for d in sorted(os.listdir(B)):
  f=f'{B}/{d}/boxscores.json.gz'
  if not os.path.exists(f): continue
  box=json.load(gzip.open(f))
  sb=f'{B}/{d}/scoreboard_final.json.gz'
  res={}
  if os.path.exists(sb):
    for e in json.load(gzip.open(sb))['events']:
      c=e['competitions'][0]
      if c['status']['type'].get('completed'):
        sc={x['team']['id']:int(x.get('score') or 0) for x in c['competitors']}
        res[e['id']]=sc
  for eid,x in box.items():
    if eid not in res: continue
    sc=res[eid]
    for p in x.get('players',[]):
      tid=p['team']['id']; name=p['team'].get('location') or p['team']['displayName']
      TM[tid]=p['team']['displayName']
      opp=[k for k in sc if k!=tid]; 
      if not opp: continue
      won=sc[tid]>sc[opp[0]]
      for g in p['statistics']:
        if g['name']!='passing': continue
        rows=[]
        for a in g['athletes']:
          s=a['stats']; 
          try: c,att=map(int,s[0].split('/')); yds=int(float(s[1])); td=int(s[3]); it=int(s[4])
          except Exception: continue
          rows.append((a['athlete']['displayName'],att,c,yds,td,it))
        if rows: games.append(dict(date=d,eid=eid,tid=tid,won=won,pf=sc[tid],pa=sc[opp[0]],rows=rows))
by=collections.defaultdict(list)
for g in games: by[g['tid']].append(g)
out={}
for tid,gs in by.items():
  gs.sort(key=lambda g:g['date']); att=collections.Counter()
  for g in gs:
    for r in g['rows']: att[r[0]]+=r[1]
  tot=sum(att.values()); qb1,a1=att.most_common(1)[0]
  last=gs[-1]; lp=max(last['rows'],key=lambda r:r[1])[0]
  starts=[g for g in gs if max(g['rows'],key=lambda r:r[1])[0]==lp]
  w=sum(g['won'] for g in starts); st=[r for g in starts for r in g['rows'] if r[0]==lp]
  qb1g=[g for g in gs if max(g['rows'],key=lambda r:r[1])[0]==qb1]
  out[tid]=dict(espn=TM[tid],qb1=qb1,share=round(a1/tot,2),last=lp,last_date=last['date'],games=len(gs),
     last_starts=len(starts),last_rec=f"{w}-{len(starts)-w}",last_line=f"{sum(r[2] for r in st)} of {sum(r[1] for r in st)}, {sum(r[3] for r in st)} yards, {sum(r[4] for r in st)} TD, {sum(r[5] for r in st)} INT",
     qb1_starts=len(qb1g),qb1_rec=f"{sum(g['won'] for g in qb1g)}-{len(qb1g)-sum(g['won'] for g in qb1g)}",
     last_games=[f"{g['date']} {'W' if g['won'] else 'L'} {g['pf']}-{g['pa']}" for g in starts][-4:],
     second=[(n,round(a/tot,2)) for n,a in att.most_common(3)[1:]])
json.dump(out,open(sys.argv[1],'w'),indent=0)
print(len(out))
