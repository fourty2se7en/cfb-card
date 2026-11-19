"""Expert consensus, follow or fade: for each game-week, the share of graded expert spread picks on each side.
Halves: weeks 1-4 / 5-7. Also the record-weighted version and the consensus vs the card's other signals."""
import math, pandas as pd, numpy as np, nflreadpy as nfl, nflmodel as M
H = pd.read_csv('experts_hist.csv')
S = nfl.load_schedules([2026]).to_pandas(); S = S[S.result.notna()]
F = {(r.away_team + '@' + r.home_team, r.week): r for r in S.itertuples()}
sp = H[(H.market == 'spread') & H.result.isin(['win', 'loss', 'push'])].copy()
sp['team'] = sp.side.map(M.canon_team)
rows = []
for (g, w), d in sp.groupby(['game', 'week']):
    a, h = (M.canon_team(x) for x in g.split('@')); r = F.get((f'{a}@{h}', w))
    if r is None or len(d) < 3: continue
    nh = (d.team == h).sum(); n = len(d); share_h = nh/n
    cov = np.sign(r.result - r.spread_line)    # +1 home covers the closing line
    rows.append(dict(week=w, n=n, share_h=share_h, cover=cov))
T = pd.DataFrame(rows); T = T[T.cover != 0]
def rep(lbl, side):
    for nm, f in (('1-4', T.week <= 4), ('5-7', T.week >= 5), ('all', T.week > 0)):
        m = (side != 0) & f; c = T.cover[m]*side[m]; n = len(c)
        if n == 0: continue
        p = (c > 0).mean(); se = math.sqrt(p*(1-p)/n)
        print(f'{lbl:48s} {nm:4s} n={n:3d} hit={p:.3f} ci=({p-1.96*se:.3f},{p+1.96*se:.3f})')
print('games with 3+ expert spread picks:', len(T))
for t in (0.6, 0.7, 0.8):
    fol = np.where(T.share_h >= t, 1, np.where(T.share_h <= 1-t, -1, 0))
    rep(f'Follow consensus {int(t*100)}%+ (vs closing line)', fol)
    rep(f'Fade consensus {int(t*100)}%+', -fol)

# Consensus against the card's other history-backed side signals: does it add anything when it agrees or disagrees?
import json, subprocess
R = {}
for c in subprocess.run(['git', '-C', '../nfl-card', 'log', '--format=%h', '--', 'scripts/nfl_power_rankings.json'], capture_output=True, text=True).stdout.split():
    try: d = json.loads(subprocess.run(['git', '-C', '../nfl-card', 'show', f'{c}:scripts/nfl_power_rankings.json'], capture_output=True, text=True).stdout)
    except Exception: continue
    R.setdefault(d['week'], d['ranks'])
rows2 = []
for (g, w), d in sp.groupby(['game', 'week']):
    a, h = (M.canon_team(x) for x in g.split('@')); r = F.get((f'{a}@{h}', w))
    if r is None or len(d) < 3: continue
    share_h = (d.team == h).mean(); fol = 1 if share_h >= .6 else -1 if share_h <= .4 else 0
    if fol == 0: continue
    cov = np.sign(r.result - r.spread_line)
    if cov == 0: continue
    rk = R.get(w); prf = 0
    if rk and a in rk and h in rk:
        gap = rk[a] - rk[h]; prf = -1 if gap >= 5 else 1 if gap <= -5 else 0   # fade the higher-ranked side
    dd = 0
    if r.div_game == 1 and r.spread_line != 0: dd = 1 if r.spread_line < 0 else -1   # home is dog when spread_line<0
    rows2.append(dict(week=w, fol=fol, cv=cov, prf=prf, dd=dd))
U = pd.DataFrame(rows2)
def rr(lbl, m):
    c = (U.cv*U.fol)[m]; n = len(c)
    if n: p = (c > 0).mean(); print(f'{lbl:55s} n={n:3d} hit={p:.3f}')
print('\nConsensus 60%+ against the other signals')
rr('consensus agrees with NFL.com-rankings fade', (U.prf != 0) & (U.prf == U.fol))
rr('consensus disagrees with NFL.com-rankings fade', (U.prf != 0) & (U.prf != U.fol))
rr('consensus with no rankings signal', U.prf == 0)
rr('consensus on the division dog', (U.dd != 0) & (U.dd == U.fol))
rr('consensus against the division dog', (U.dd != 0) & (U.dd != U.fol))
