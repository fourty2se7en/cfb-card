"""Do NFL.com's weekly power rankings carry information the closing line does not? Each week's list (git history of
scripts/nfl_power_rankings.json, published Tuesday, before the games) against that week's results."""
import json, subprocess, math, pandas as pd, numpy as np, nflreadpy as nfl
R = {}
for c in subprocess.run(['git', '-C', '../nfl-card', 'log', '--format=%h', '--', 'scripts/nfl_power_rankings.json'], capture_output=True, text=True).stdout.split():
    try: d = json.loads(subprocess.run(['git', '-C', '../nfl-card', 'show', f'{c}:scripts/nfl_power_rankings.json'], capture_output=True, text=True).stdout)
    except Exception: continue
    R.setdefault(d['week'], d['ranks'])
S = nfl.load_schedules([2026]).to_pandas(); S = S[(S.game_type == 'REG') & S.result.notna()]
rows = []
for g in S.itertuples():
    rk = R.get(g.week)
    if not rk or g.home_team not in rk or g.away_team not in rk: continue
    gap = rk[g.away_team] - rk[g.home_team]          # >0: NFL.com ranks the home team higher
    cover = np.sign(g.result - g.spread_line)
    rows.append(dict(week=g.week, gap=gap, cover=cover, fav_home=g.spread_line > 0, spread=g.spread_line))
T = pd.DataFrame(rows); T = T[T.cover != 0]
def rep(lbl, side):
    m = side != 0; c = T.cover[m]*side[m]; n = len(c); p = (c > 0).mean(); se = math.sqrt(p*(1-p)/n)
    print(f'{lbl:60s} n={n:3d} hit={p:.3f} ci=({p-1.96*se:.3f},{p+1.96*se:.3f})')
print('weeks', sorted(T.week.unique()), 'games', len(T))
for t in (1, 5, 10):
    rep(f'Back the team NFL.com ranks {t}+ spots higher', np.where(T.gap >= t, 1, np.where(T.gap <= -t, -1, 0)))
# ranked higher but getting points (NFL.com disagrees with the market's favourite)
rep('NFL.com ranks the underdog higher: back the dog', np.where((T.gap > 0) & (T.spread < 0), 1, np.where((T.gap < 0) & (T.spread > 0), -1, 0)))
print('--- fade, by half (weeks 2-4 / 5-7)')
for t in (5, 10):
    side = np.where(T.gap >= t, -1, np.where(T.gap <= -t, 1, 0))
    for lbl, f in (('2-4', T.week <= 4), ('5-7', T.week >= 5)):
        m = (side != 0) & f; c = T.cover[m]*side[m]; print(f'fade {t}+ weeks {lbl}: n={len(c)} hit={(c>0).mean():.3f}')
