import csv,gzip,glob,json,sys,statistics as st,collections,re,os
day,pend,gradef,out=sys.argv[1:5]
rows=[]
for f in sorted(glob.glob(f'/home/claude/cfb14_nba/odds/data/nba/{day}/close*.csv.gz')):
    for r in csv.DictReader(gzip.open(f,'rt')):
        if r['snap']<=r['commence']: rows.append(r)
# latest snap per (event,book,market,outcome,player)
last={}
for r in rows:
    k=(r['away'],r['home'],r['book'],r['market'],r['outcome'],r['player'])
    if k not in last or r['snap']>last[k]['snap']: last[k]=r
by=collections.defaultdict(list)
for k,r in last.items(): by[(r['away'],r['home'],r['market'],r['outcome'],r['player'])].append(r)
def imp(p): p=float(p); return 100/(p+100) if p>0 else -p/(-p+100)
def med_price(ps):
    dec=[1+p/100 if p>0 else 1+100/-p for p in ps]; m=st.median(dec)
    return round((m-1)*100) if m>=2 else round(-100/(m-1))
def close(away,home,market,outcome,player=''):
    L=by.get((away,home,market,outcome,player))
    if player: L=[r for k,v in by.items() if k[2:]==(market,outcome,player) for r in v]
    if not L: return None
    pts=collections.Counter(r['point'] for r in L); pt=pts.most_common(1)[0][0]
    ps=[float(r['price']) for r in L if r['point']==pt]
    return (float(pt) if pt else None, med_price(ps))
NB={}
upd={u['id']:u for u in json.load(open(gradef))['updates']}
res=[]
statm={'points':'player_points','rebounds':'player_rebounds','assists':'player_assists','threes':'player_threes','3-pointers made':'player_threes'}
for f in sorted(glob.glob(pend+'/*.json')):
    did=os.path.basename(f)[:-5]; d=json.load(open(f)); d=d.get('data',d)
    teams=[x for x in last.values()]
    # find full names from game text
    gm=None
    for (a,h,*_ ) in by:
        pass
    ev=[k for k in by if k[0] and k[1]]
    # map via doc full names
    awayN=d.get('away_name') or ''
    cand=set((k[0],k[1]) for k in by)
    m=d.get('market'); pk=d.get('pick','')
    # match game by codes in team names list
    sys.path.insert(0,'/home/claude/nba14r2/run/w'); from teams import FULL
    gm=None
    ga,gh=FULL.get(d.get('away'),'?'),FULL.get(d.get('home'),'?')
    if (ga,gh) in cand: gm=(ga,gh)
    for a,h in ([] if gm else cand):
        if (d.get('team_name') and d['team_name'] in (a,h)) or any(w in pk for w in (a,h)):
            gm=(a,h)
    if gm is None and m=='Prop': gm=next(iter(cand))
    if gm is None:
        # match by nickname tokens of game string
        for a,h in cand:
            if a.split()[-1] in json.dumps(d) and h.split()[-1] in json.dumps(d): gm=(a,h)
    c=None; clv=None
    if gm:
        a,h=gm
        if m=='Total':
            side='Under' if pk.startswith('Under') else 'Over'; c=close(a,h,'totals',side)
            if c and c[0] is not None: clv=round((c[0]-d['line']) if side=='Under' else (d['line']-c[0]),1)
        elif m=='Spread':
            team=a if a in pk else h; c=close(a,h,'spreads',team)
            if c: clv=round(d['line']-c[0],1)
        elif m=='Moneyline':
            team=a if a in pk else h; c=close(a,h,'h2h',team)
            if c: clv=round((imp(c[1])-imp(d['price']))*100,1)
        elif m=='Prop':
            side='Over' if d.get('side','').lower()=='over' else 'Under'
            c=close(a,h,statm.get(d.get('stat'),'x'),side,d.get('player',''))
            if c and c[0] is not None and c[0]==float(d['line']): clv=round((imp(c[1])-imp(d['price']))*100,1)
            elif c and c[0] is not None:
                clv=round((c[0]-float(d['line'])) if side=='Over' else (float(d['line'])-c[0]),1)
    u=upd[did]; u['close_line']=c[0] if c else None; u['close_price']=c[1] if c else None; u['clv']=clv
    res.append(u); print(did[11:],m,d.get('line'),d.get('price'),'close',c,'clv',clv)
json.dump(res,open(out,'w'),indent=1)
