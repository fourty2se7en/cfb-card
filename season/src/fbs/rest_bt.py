"""Short-week re-test (Nov 2, 2026): the original signal counted rest as UTC-date differences,
so most 'short weeks' were normal Saturday-to-Saturday weeks with an earlier kickoff.
This compares that definition with real calendar days (US Eastern date) and with hours of rest.
FBS vs FBS (and FCS vs FCS for reference), regular season 2017-2025 + 2026 to date, consensus closing spread."""
import gzip, json, math, sys
from pathlib import Path
import numpy as np, pandas as pd
BT = Path(__file__).parent.parent / 'bt'; REPO = Path(__file__).parent / 'repo'

def load(kind, y):
    try: return json.load(gzip.open(BT / f'{kind}_{y}.json.gz'))
    except FileNotFoundError: return []

G = []
for y in range(2016, 2026):
    for g in load('games', y):
        if g.get('seasonType') != 'regular' or g.get('homePoints') is None or g.get('awayPoints') is None: continue
        G.append(dict(id=g['id'], season=y, week=g['week'], start=g['startDate'], home=g['homeTeam'], away=g['awayTeam'],
                      hc=g.get('homeClassification'), ac=g.get('awayClassification'), margin=g['homePoints'] - g['awayPoints']))
G = pd.DataFrame(G)
SP = {}
for y in range(2016, 2026):
    for l in load('lines', y):
        s = [x['spread'] for x in (l.get('lines') or []) if x.get('spread') is not None]
        if s: SP[l['id']] = float(np.median(s))
G['spread'] = G.id.map(SP)
# 2026 to date from the repo
g26 = pd.read_csv(REPO / 'games.csv'); g26 = g26[(g26.season == 2026) & (g26.seasonType == 'regular') & g26.homePoints.notna()]
L26 = pd.read_csv(REPO / 'lines.csv'); L26 = L26[L26.season == 2026]
import ast
sp26 = {}
for r in L26.itertuples():
    try: ls = ast.literal_eval(r.lines) if isinstance(r.lines, str) else []
    except Exception: ls = []
    s = [x['spread'] for x in ls if x.get('spread') is not None]
    if s: sp26[int(r.id)] = float(np.median(s))
G = pd.concat([G, pd.DataFrame(dict(id=g26.id, season=2026, week=g26.week, start=g26.startDate, home=g26.homeTeam, away=g26.awayTeam,
      hc=g26.homeClassification, ac=g26.awayClassification, margin=g26.homePoints - g26.awayPoints, spread=g26.id.map(sp26)))], ignore_index=True)
G['ts'] = pd.to_datetime(G.start, utc=True)
G['utc_day'] = pd.to_datetime(G.start.str[:10])
G['et_day'] = G.ts.dt.tz_convert('America/New_York').dt.tz_localize(None).dt.normalize()
G = G.sort_values('ts')

last = {}
rows = []
for r in G.itertuples():
    feats = {}
    for k, t in (('h', r.home), ('a', r.away)):
        p = last.get((r.season, t))
        if p is not None:
            feats['utc_' + k] = (r.utc_day - p[0]).days
            feats['cal_' + k] = (r.et_day - p[1]).days
            feats['hrs_' + k] = (r.ts - p[2]).total_seconds() / 3600
    if r.spread == r.spread and len(feats) == 6:
        rows.append(dict(season=r.season, div='fbs' if (r.hc == 'fbs' and r.ac == 'fbs') else ('fcs' if (r.hc == 'fcs' and r.ac == 'fcs') else 'x'),
                         spread=r.spread, cover=np.sign(r.margin + r.spread), **feats))
    for t in (r.home, r.away): last[(r.season, t)] = (r.utc_day, r.et_day, r.ts)
T = pd.DataFrame(rows)

def rate(side, f):
    m = side != 0; c = f.cover[m] * side[m]; c = c[c != 0]
    n = len(c); k = int((c > 0).sum())
    if not n: return n, float('nan'), float('nan'), float('nan')
    p = k / n; se = math.sqrt(p * (1 - p) / n); return n, p, p - 1.96 * se, p + 1.96 * se

def sig(f, col, short, normal):
    a, h = f[col + '_a'], f[col + '_h']
    return np.where((a <= short) & (h >= normal), 1, np.where((h <= short) & (a >= normal), -1, 0))

def dog(f, side): return np.where((side == 1) & (f.spread > 0), 1, np.where((side == -1) & (f.spread < 0), -1, 0))

DEFS = [('Original: UTC dates, 6 days or less vs 7+', 'utc', 6, 7),
        ('Calendar days (Eastern), 6 days or less vs 7+', 'cal', 6, 7),
        ('Real short week: calendar 5 days or less vs 6+', 'cal', 5, 6),
        ('Hours: opponent under 156 h (6.5 days), team 156 h+', 'hrs', 155.99, 156)]
out = []
for div in ('fbs', 'fcs'):
    F = T[T['div'] == div]
    for name, col, s, nrm in DEFS:
        sd = sig(F, col, s, nrm)
        for lab, x in (('all', sd), ('underdog only', dog(F, sd))):
            for per, msk in (('2017-2025', F.season <= 2025), ('2026', F.season == 2026)):
                n, p, lo, hi = rate(x[msk.values], F[msk])
                out.append(dict(div=div, definition=name, side=lab, period=per, n=n, cover=round(p, 3) if n else None, lo=round(lo, 3) if n else None, hi=round(hi, 3) if n else None))
R = pd.DataFrame(out)
pd.set_option('display.width', 250); pd.set_option('display.max_colwidth', 60)
print(R.to_string(index=False))
R.to_csv(Path(__file__).parent / 'rest_bt.csv', index=False)
print('dist utc rest fbs', T[T['div']=='fbs'].utc_a.value_counts().sort_index().loc[3:9].to_dict())
print('dist cal rest fbs', T[T['div']=='fbs'].cal_a.value_counts().sort_index().loc[3:9].to_dict())
