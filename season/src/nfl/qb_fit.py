"""Measure what a QB change is worth in points: home margin ~ pre-game Elo gap + QB-change flags, 2006-2025.
Elo as in elo.py (results only), so the QB effect is not already inside the predictor."""
import numpy as np, pandas as pd
from sklearn.linear_model import LinearRegression
T = pd.read_csv('sig_rows.csv')
S = __import__('nflreadpy').load_schedules(list(range(2005, 2026))).to_pandas()
S = S[S.game_type.isin(['REG','WC','DIV','CON','SB'])].sort_values(['season','week'])
FIX = {'OAK':'LV','SD':'LAC','STL':'LA','LAR':'LA'}
elo, last, pre = {}, None, {}
for g in S[S.result.notna()].itertuples():
    if g.season != last:
        for t in elo: elo[t] = 1500 + (elo[t]-1500)*0.75
        last = g.season
    h, a = FIX.get(g.home_team, g.home_team), FIX.get(g.away_team, g.away_team)
    eh, ea = elo.setdefault(h, 1500), elo.setdefault(a, 1500)
    hadv = 0 if g.location == 'Neutral' else 48
    pre[(g.season, g.week, h, a)] = (eh + hadv - ea)/25
    m = g.home_score - g.away_score; exp = 1/(1+10**(-(eh+hadv-ea)/400))
    mov = np.log(abs(m)+1)*(2.2/(abs(eh+hadv-ea)*0.001+2.2))
    d = 20*mov*((m>0)+0.5*(m==0)-exp); elo[h] = eh+d; elo[a] = ea-d
T['elo'] = [pre.get((r.season, r.week, r.h, r.a)) for r in T.itertuples()]
X = T.dropna(subset=['elo']); y = X.margin
F = np.column_stack([X.elo, X.qbchg_h.astype(float), X.qbchg_a.astype(float)])
m = LinearRegression().fit(F, y)
res = y - m.predict(F); s2 = (res**2).sum()/(len(y)-4)
cov = s2*np.linalg.inv(np.column_stack([np.ones(len(y)), F]).T @ np.column_stack([np.ones(len(y)), F]))
se = np.sqrt(np.diag(cov))
print('n', len(y), 'coef elo', round(m.coef_[0],3), 'home QB change', round(m.coef_[1],2), '+-', round(1.96*se[2],2), 'away QB change', round(m.coef_[2],2), '+-', round(1.96*se[3],2))
