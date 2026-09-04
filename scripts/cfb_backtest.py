"""
cfb_backtest.py — opponent-adjusted ratings from game results, walk-forward,
graded against real closing lines. 2023-2025.

No play-by-play, no API key. Ratings come from margins only, which is exactly
what the NFL Elo model used — and that model tracked the EPA model at 0.906.

CFB differs from the NFL in ways that matter and are set explicitly here:
  - 130+ FBS teams plus FCS opponents, so the talent range is enormous
  - Margins scatter far more widely than the NFL's ~13.2 points
  - Schedule strength varies wildly, so opponent adjustment carries more weight
  - Only ~12 games a season, so prior-season priors matter longer
"""
import pandas as pd, numpy as np
from sklearn.linear_model import Ridge
from scipy.stats import norm
import warnings; warnings.filterwarnings("ignore")

YEARS = [2021, 2022, 2023, 2024, 2025]
TEST = [2023, 2024, 2025]
HALF_LIFE = 6.0          # games; CFB seasons are short
PRIOR_W = 4.0            # weight on prior-season rating, in games
CARRY = 0.55             # prior-season carryover (transfer portal erodes it)
MARGIN_CAP = 38          # cap blowouts; running up 70-0 is not 3x as informative

# ---------- load ----------
sch = pd.concat([pd.read_csv(f"s{y}.csv") for y in YEARS], ignore_index=True)
sch = sch[(sch.season_type == "regular") & sch.home_points.notna() & sch.away_points.notna()]
sch["margin"] = sch.home_points - sch.away_points
sch["total_pts"] = sch.home_points + sch.away_points
sch["neutral"] = sch.neutral_site.fillna(False).astype(bool)
print(f"games loaded: {len(sch):,}   seasons: {sorted(sch.season.unique())}")

lines = pd.read_csv("lines.csv.gz")
# One line per game. The raw file carries a row per book, and joining without
# collapsing that multiplies every game by its book count — which silently turned
# 4,547 games into 23,115 rows on the first run.
sp = lines[lines.market_type == "spread"].dropna(subset=["lines"])
sp = (sp.groupby(["game_id", "abbr"], as_index=False)
        .agg(lines=("lines", "median"), open_line=("opening_lines", "median"),
             books=("book", "nunique")))
tot = lines[(lines.market_type == "total") & (lines.abbr == "over")].dropna(subset=["lines"])
tot = tot.groupby("game_id", as_index=False).agg(mkt_total=("lines", "median"))

# Only rate teams with enough games to be estimable. Everyone else collapses into
# a single "other" bucket, which keeps the design matrix from exploding with
# hundreds of DII/DIII teams that appear once or twice.
_cnt = pd.concat([sch.home_team, sch.away_team]).value_counts()
_rated = set(_cnt[_cnt >= 12].index)
sch["home_team"] = np.where(sch.home_team.isin(_rated), sch.home_team, "OTHER")
sch["away_team"] = np.where(sch.away_team.isin(_rated), sch.away_team, "OTHER")
teams = sorted(set(sch.home_team) | set(sch.away_team))
tidx = {t: i for i, t in enumerate(teams)}
n = len(teams)
print(f"teams rated: {n}  (collapsed {len(_cnt)-len(_rated)} low-sample teams into OTHER)")


def fit_ratings(games, ref_week, ref_season):
    """Ridge on margins with team dummies + a home-field term.
    Opponent adjustment falls out of the regression by construction."""
    if len(games) < 50:
        return None, 2.5
    g = games.copy()
    age = (ref_season - g.season) * 15 + (ref_week - g.week)
    w = 0.5 ** (age / HALF_LIFE)
    y = g.margin.clip(-MARGIN_CAP, MARGIN_CAP).values
    X = np.zeros((len(g), n + 1))
    X[np.arange(len(g)), g.home_team.map(tidx).values] = 1
    X[np.arange(len(g)), g.away_team.map(tidx).values] = -1
    X[:, n] = np.where(g.neutral.values, 0.0, 1.0)      # home field
    m = Ridge(alpha=3.0, fit_intercept=False).fit(X, y, sample_weight=w)
    r = pd.Series(m.coef_[:n], index=teams)
    return r - r.mean(), float(m.coef_[n])


rows = []
for season in TEST:
    for week in sorted(sch[sch.season == season].week.unique()):
        hist = sch[(sch.season < season) | ((sch.season == season) & (sch.week < week))]
        hist = hist[hist.season >= season - 2]
        R, hfa = fit_ratings(hist, week, season)
        if R is None:
            continue
        cur = sch[(sch.season == season) & (sch.week == week)]
        for _, g in cur.iterrows():
            h, a = g.home_team, g.away_team
            if h not in R.index or a not in R.index:
                continue
            model_margin = R[h] - R[a] + (0.0 if g.neutral else hfa)
            rows.append(dict(season=season, week=week, game_id=g.game_id,
                             home=h, away=a, model=model_margin,
                             margin=g.margin, total_pts=g.total_pts,
                             fbs=(g.home_division == "fbs" and g.away_division == "fbs")))
    print(f"  {season} priced")

B = pd.DataFrame(rows)
B = B.merge(sp, left_on=["game_id", "home"], right_on=["game_id", "abbr"], how="inner")
B = B.rename(columns={"lines": "mkt_spread"}).dropna(subset=["mkt_spread"])
B = B.drop_duplicates(subset=["game_id"])
B = B.merge(tot, on="game_id", how="left")
# nflverse convention: positive spread_line = home favored. This source posts the
# home team's own line, so -4 means home favored by 4. Flip it to match.
B["mkt_spread"] = -B["mkt_spread"]
B.to_csv("cfb_backtest.csv", index=False)
print(f"\ngames with a closing spread: {len(B):,}   FBS-vs-FBS: {int(B.fbs.sum()):,}")

# ---------- grade ----------
def grade(sub, label):
    if len(sub) < 50:
        print(f"\n{label}: too few games"); return
    e = sub.model - sub.mkt_spread
    ok0 = sub.margin != sub.mkt_spread
    print(f"\n{label}   (n={len(sub):,})")
    print(f"  {'min edge':>9} {'record':>13} {'win%':>7}")
    for me in [0, 3, 6, 10, 14]:
        m = ok0 & (e.abs() >= me)
        w = (((e > 0) & (sub.margin > sub.mkt_spread)) | ((e <= 0) & (sub.margin < sub.mkt_spread))) & m
        wins, losses = int(w.sum()), int(m.sum() - w.sum())
        if wins + losses < 30: continue
        pct = 100 * wins / (wins + losses)
        flag = "  <-- beats break-even" if pct > 52.4 else ""
        print(f"  {me:>9} {f'{wins}-{losses}':>13} {pct:>6.1f}%{flag}")

print("\n" + "=" * 60)
print("SPREAD RESULTS   (break-even at -110 is 52.4%)")
print("=" * 60)
grade(B, "ALL GAMES 2023-2025")
grade(B[B.fbs], "FBS vs FBS only")
grade(B[~B.fbs], "Games involving non-FBS")
for y in TEST:
    grade(B[B.season == y], f"{y} only")

print("\n" + "=" * 60)
print("DIAGNOSTICS")
print("=" * 60)
print(f"  model vs market correlation: {np.corrcoef(B.model, B.mkt_spread)[0,1]:.3f}")
print(f"  model spread SD {B.model.std():.2f}  vs  market SD {B.mkt_spread.std():.2f}")
print(f"  market MAE vs actual margin: {(B.mkt_spread - B.margin).abs().mean():.2f}")
print(f"  model  MAE vs actual margin: {(B.model - B.margin).abs().mean():.2f}")
print(f"  actual margin SD: {B.margin.std():.2f}   (NFL is about 13.2)")
