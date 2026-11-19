import sys, json, collections
sys.path.insert(0, '/home/claude/season/nba/w')
import newrules as NR, season_build as SB, pickrules as P
today = sys.argv[1]
G = SB.build(); rows = []; Ss = []
for g in G:
    r = NR.row(g); r['g'] = f"{g['a']}-{g['h']}"; rows.append(r); Ss.append(P.score_game(g['inp']))
print('season games', len(G), max(g['d'] for g in G))
RES = {}
for k in NR.DEF:
    L, _ = NR.replay(rows, Ss, k); by = collections.defaultdict(list)
    for x in L: by[x['tier']].append(x)
    RES[k] = dict(season=NR.rec(L), n=len(L), tiers={t: dict(season=NR.rec(v), n=len(v), month=NR.rec([x for x in v if x['date'] >= today[:7]])) for t, v in by.items()})
    print(k, NR.rec(L), {t: (lambda q: f"{q['w']}-{q['l']} {q['u']:+.2f}u")(NR.rec(v)) for t, v in sorted(by.items())})
json.dump(dict(replay=RES), open('/home/claude/season/nba/newrules_replay.json', 'w'), indent=1)
TI = json.load(open('/home/claude/season/nba/w/today_inp.json'))
F = NR.today_fits(today, rows, Ss, TI)
json.dump(F, open('/home/claude/season/nba/newrules_today.json', 'w'), indent=1)
for f in F: print(f['game'], f['rule'], f['market'], f['side'], f.get('line'), f['price'], f['tier'], f['lead'], f.get('edge'))
