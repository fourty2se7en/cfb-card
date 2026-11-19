"""
elo.py — independent Elo ratings from game results only.
Deliberately uses NO EPA, so disagreement with the main model is
informative rather than circular. Acts as a bug detector.
"""
import nflreadpy as nfl
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')
import os
BASE = os.environ.get("NFL_DIR") or os.path.dirname(os.path.abspath(__file__))
P = lambda x: os.path.join(BASE, x)


K, HFA_ELO, REVERT = 20.0, 48.0, 0.25
START = 1500.0

sch = nfl.load_schedules(list(range(2015, 2027))).to_pandas()
sch = sch[sch.game_type.isin(["REG", "WC", "DIV", "CON", "SB"])].sort_values(["season", "week"])
played = sch[sch.result.notna()]

elo, last_season = {}, None
for _, g in played.iterrows():
    if g.season != last_season:
        for t in elo:                       # offseason regression to mean
            elo[t] = START + (elo[t] - START) * (1 - REVERT)
        last_season = g.season
    h, a = g.home_team, g.away_team
    eh = elo.setdefault(h, START); ea = elo.setdefault(a, START)
    hadv = 0.0 if str(g.location) == "Neutral" else HFA_ELO
    exp_h = 1 / (1 + 10 ** (-(eh + hadv - ea) / 400))
    margin = g.home_score - g.away_score
    actual = 1.0 if margin > 0 else (0.5 if margin == 0 else 0.0)
    # margin-of-victory multiplier, damped for elo autocorrelation
    mov = np.log(abs(margin) + 1) * (2.2 / ((abs(eh + hadv - ea)) * 0.001 + 2.2))
    delta = K * mov * (actual - exp_h)
    elo[h] = eh + delta; elo[a] = ea - delta

E = pd.Series(elo).sort_values(ascending=False)
E.name = "elo"
E.to_csv(P("elo_ratings.csv"))
print(f"teams: {len(E)}   range {E.min():.0f}-{E.max():.0f}")
print("\nTOP 5"); print(E.head(5).round(0).to_string())
print("\nBOTTOM 5"); print(E.tail(5).round(0).to_string())

# agreement with the EPA-based ratings
r = pd.read_csv(P("power_ratings.csv"), index_col=0)
r["rating"] = r.Off2025 * 0.65 + r.Def2025 * 0.55
j = pd.DataFrame({"elo_pts": (E - E.mean()) / 25.0, "epa_pts": r.rating}).dropna()
print(f"\nElo vs EPA-model correlation: {j.corr().iloc[0,1]:.3f}")
print("(low correlation = the two methods disagree; treat those teams with caution)")
d = (j.elo_pts - j.epa_pts).abs().sort_values(ascending=False)
print("\nBIGGEST DISAGREEMENTS (flag for review)")
print(pd.DataFrame({"elo_pts": j.elo_pts.round(1), "epa_pts": j.epa_pts.round(1),
                    "diff": d.round(1)}).loc[d.head(6).index].to_string())
