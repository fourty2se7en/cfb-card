"""Grade every expert pick the GitHub card logged (scripts/expert_picks.csv, weeks 1-7 settled) and test,
walk-forward, whether an expert's record so far predicts his next week. Spread/total graded at the pick's own
line; moneyline graded straight up. Prices are not stored, so ATS/total use -110 break-even 52.4% and moneyline
is reported as win rate vs the de-vigged closing price (nflverse)."""
import math, sys, pandas as pd, numpy as np, nflreadpy as nfl
sys.path.insert(0, '.'); import nflmodel as M
E = pd.read_csv('../nfl-card/scripts/expert_picks.csv')
S = nfl.load_schedules([2026]).to_pandas(); S = S[S.result.notna()]
S['key'] = S.away_team + '@' + S.home_team
F = S.set_index('key')
rows = []
for r in E.itertuples():
    k = r.game
    a, h = (M.canon_team(x) for x in k.split('@'))
    k = f'{a}@{h}'
    if k not in F.index: continue
    g = F.loc[k]
    if isinstance(g, pd.DataFrame): g = g[g.week == r.week].iloc[0]
    hm = g.home_score - g.away_score; tot = g.home_score + g.away_score
    side = str(r.side).strip(); res = None; p_mkt = None
    if r.market == 'spread':
        t = M.canon_team(side); line = float(r.line)
        m = hm if t == h else -hm
        res = np.sign(m + line)
    elif r.market == 'total':
        line = float(r.line); res = np.sign(tot - line) * (1 if side.lower() == 'over' else -1)
    elif r.market == 'moneyline':
        t = M.canon_team(side); m = hm if t == h else -hm; res = np.sign(m)
        ma, mh = g.away_moneyline, g.home_moneyline
        if pd.notna(ma) and pd.notna(mh):
            ia, ih = M.amp(ma), M.amp(mh); p_mkt = (ih if t == h else ia)/(ia+ih)
    rows.append(dict(week=r.week, name=r.name, market=r.market, res=res, p_mkt=p_mkt))
T = pd.DataFrame(rows); T = T[T.res != 0]
T['w'] = (T.res > 0).astype(int)
print('graded', len(T), 'of', len(E), 'by market:', T.groupby('market').w.agg(['count', 'mean']).round(3).to_dict('index'))
ats = T[T.market.isin(['spread', 'total'])]
print('ALL experts ATS+totals', len(ats), round(ats.w.mean(), 3))
ml = T[T.market == 'moneyline'].dropna(subset=['p_mkt'])
print('ALL experts ML win', len(ml), round(ml.w.mean(), 3), 'vs priced', round(ml.p_mkt.mean(), 3))
# walk-forward: rate each expert on weeks < w (shrunk 10 picks at .500), test week w picks
out = []
for w in range(3, 8):
    prior = ats[ats.week < w]; test = ats[ats.week == w]
    rec = prior.groupby('name').w.agg(['sum', 'count'])
    rec['shr'] = (rec['sum'] + 5)/(rec['count'] + 10)
    for r in test.itertuples():
        s = rec.shr.get(r.name, 0.5); n = rec['count'].get(r.name, 0)
        out.append(dict(week=w, name=r.name, shr=s, n=n, w=r.w))
O = pd.DataFrame(out)
def show(lbl, m):
    x = O[m]; n = len(x); p = x.w.mean() if n else float('nan'); se = math.sqrt(p*(1-p)/n) if n else 0
    print(f'{lbl:55s} n={n:4d} hit={p:.3f} ci=({p-1.96*se:.3f},{p+1.96*se:.3f})')
show('Walk-forward test picks, all', O.w >= 0)
show('Expert with prior shrunk record >= .524', O.shr >= .524)
show('Expert with prior shrunk record >= .55', O.shr >= .55)
show('Expert with prior shrunk record < .50', O.shr < .50)
show('Expert with no prior record', O.n == 0)
# per expert season table
tab = ats.groupby('name').w.agg(['sum', 'count']); tab['pct'] = tab['sum']/tab['count']
print(tab.sort_values('count', ascending=False).head(15).to_string())
