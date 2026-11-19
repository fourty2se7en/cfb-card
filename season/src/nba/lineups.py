"""Lineups text for post2.py from the repo player_logs.json.gz: TEAM#name~mpg_last5~rating~strengths~weaknesses~X;...
rating = league percentile of a per 36 composite (pts + 1.2 reb + 1.5 ast + 2 stl + 2 blk - tov); strengths top quarter per 36."""
import gzip, json, sys, collections
pl = json.load(gzip.open(sys.argv[1]))['players']; slate = sys.argv[2].split(','); out = sys.argv[3]
cur = {}
for p in pl.values():
    G = [g for g in p['games'] if g['date'] >= '2026-10-01']
    if not G: continue
    t = G[-1]['team']; mins = sum(g['min'] or 0 for g in G)
    if mins < 30: continue
    s = lambda k: sum((g.get(k) or 0) for g in G) * 36 / mins
    cur[p['name']] = dict(t=t, G=G, pts=s('pts'), reb=s('reb'), ast=s('ast'), t3=s('t3m'), d=s('stl') + s('blk'), to=s('to'))
comp = {n: v['pts'] + 1.2 * v['reb'] + 1.5 * v['ast'] + 2 * v['d'] - v['to'] for n, v in cur.items()}
allc = sorted(comp.values()); pct = lambda x: int(100 * sum(1 for y in allc if y <= x) / len(allc))
def q(k, hi=True):
    v = sorted(x[k] for x in cur.values()); return v[int(len(v) * (0.75 if hi else 0.25))]
th = {k: q(k) for k in ('pts', 'reb', 'ast', 't3', 'd')}; lo_pts = q('pts', False); hi_to = q('to')
lines = []
for t in slate:
    dates = sorted({g['date'] for v in cur.values() if v['t'] == t for g in v['G'] if g['team'] == t})[-5:]
    rows = []
    for n, v in cur.items():
        if v['t'] != t: continue
        m = sum((g['min'] or 0) for g in v['G'] if g['date'] in dates and g['team'] == t) / max(len(dates), 1)
        if m < 6: continue
        st = ''.join(c for c, k in (('S', 'pts'), ('R', 'reb'), ('P', 'ast'), ('T', 't3'), ('D', 'd')) if v[k] >= th[k])
        wk = ('s' if v['pts'] <= lo_pts else '') + ('o' if v['to'] >= hi_to else '')
        rows.append((m, f"{n}~{round(m)}~{pct(comp[n])}~{st}~{wk}~"))
    rows.sort(key=lambda r: -r[0])
    lines.append(t + '#' + ';'.join(r[1] for r in rows[:11]))
open(out, 'w').write('\n'.join(lines) + '\n'); print('\n'.join(l[:160] for l in lines))
