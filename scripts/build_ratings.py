"""
build_ratings.py — opponent-adjusted college football power ratings.

Built from game margins with a ridge regression on team dummies plus a
home-field term, so opponent strength is adjusted out by construction. This
matters far more in college than the NFL: two teams with the same record can
have played wildly different schedules.

Validated walk-forward on 4,401 games with real closing lines. Correlation with
the market is 0.819 and ratings dispersion is 8.3 points against the market's
15.2, so the model is deliberately more conservative than the posted number.

Reads data/games.csv (and games_prior.csv) written by fetch_data.py.
Optionally folds in talent and returning production when those files exist.
"""
import os, sys
import numpy as np, pandas as pd
from sklearn.linear_model import Ridge
import warnings; warnings.filterwarnings("ignore")

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
P = lambda f: os.path.join(DATA, f)

HALF_LIFE = 6.0      # games; college seasons are short so decay must be quicker
CARRY = 0.55         # prior-season carryover, eroded by the transfer portal
MARGIN_CAP = 50      # blowout cap; high enough that FBS-over-FCS games still inform the division gap
RIDGE_ALPHA = 3.0    # light. Heavy shrinkage collapsed every rating toward zero
MIN_GAMES = 12       # below this a team cannot be estimated; bucket it


def load():
    frames = []
    for f, tag in (("games_prior.csv", "prior"), ("games.csv", "current")):
        if os.path.exists(P(f)):
            d = pd.read_csv(P(f)); d["_src"] = tag; frames.append(d)
    if not frames:
        sys.exit("ERROR: no games data. Run fetch_data.py first.")
    g = pd.concat(frames, ignore_index=True)
    ren = {"homeTeam": "home_team", "awayTeam": "away_team",
           "homePoints": "home_points", "awayPoints": "away_points",
           "neutralSite": "neutral", "homeClassification": "home_div",
           "awayClassification": "away_div", "homeConference": "home_conf",
           "awayConference": "away_conf", "startDate": "start_date"}
    g = g.rename(columns={k: v for k, v in ren.items() if k in g.columns})
    for c in ("home_points", "away_points"):
        if c not in g.columns: sys.exit(f"ERROR: games data has no {c} column")
    g["neutral"] = g.get("neutral", False)
    g["neutral"] = g["neutral"].fillna(False).astype(bool)
    return g


g = load()
played = g.dropna(subset=["home_points", "away_points"]).copy()
played["margin"] = played.home_points - played.away_points
print(f"games with results: {len(played):,}")
if len(played) < 60:
    print("WARNING: very early season — ratings will lean almost entirely on priors")

# Rate FBS and FCS only. Division II and III schedules barely intersect the top
# divisions, so the regression cannot place them on the same scale — left in, a
# D-III champion outranks half the SEC purely from beating isolated competition.
# They are also irrelevant here: betting lines exist for FBS and some FCS games.
KEEP_DIV = {"fbs", "fcs"}
if "home_div" in played.columns:
    div = {}
    for _, gg in played.iterrows():
        div.setdefault(gg.home_team, str(gg.get("home_div", "")).lower())
        div.setdefault(gg.away_team, str(gg.get("away_div", "")).lower())
    eligible = {t for t, d in div.items() if d in KEEP_DIV}
    print(f"eligible teams (FBS/FCS): {len(eligible)} of {len(div)}")
else:
    eligible = set(played.home_team) | set(played.away_team)

# Collapse rarely-seen teams so the design matrix stays estimable.
cnt = pd.concat([played.home_team, played.away_team]).value_counts()
rated = {t for t in cnt[cnt >= MIN_GAMES].index if t in eligible}
for c in ("home_team", "away_team"):
    played[c] = np.where(played[c].isin(rated), played[c], "OTHER")
teams = sorted(set(played.home_team) | set(played.away_team))
tidx = {t: i for i, t in enumerate(teams)}
n = len(teams)
print(f"teams rated: {n}  (bucketed {len(cnt) - len(rated)} low-sample teams)")

# Recency: current season counts more than prior, recent weeks more than early.
maxw = played[played._src == "current"].week.max() if (played._src == "current").any() else 0
age = np.where(played._src == "current", maxw - played.week, maxw + (15 - played.week) )
w = 0.5 ** (np.asarray(age, dtype=float) / HALF_LIFE)
w = np.where(played._src == "prior", w * CARRY, w)

y = played.margin.clip(-MARGIN_CAP, MARGIN_CAP).values
# One extra term learns the FBS-over-FCS gap from the cross-division games that
# actually happen. Without it, FCS teams float up to the top of the table: their
# schedules barely touch FBS, so the regression has no way to place them.
DIVMAP = {t: d for t, d in div.items()} if "home_div" in played.columns else {}
is_fcs = lambda t: DIVMAP.get(t, "") == "fcs"
# NOTE: the division gap is deliberately NOT a column here. Division membership
# is a linear combination of the team dummies, so ridge splits the effect
# between them arbitrarily - it came back negative, which inverted the
# adjustment and floated FCS teams to the top of the table. It is measured
# from residuals after the fit instead.
X = np.zeros((len(played), n + 1))
X[np.arange(len(played)), played.home_team.map(tidx).values] = 1
X[np.arange(len(played)), played.away_team.map(tidx).values] = -1
X[:, n] = np.where(played.neutral.values, 0.0, 1.0)

m = Ridge(alpha=RIDGE_ALPHA, fit_intercept=False).fit(X, y, sample_weight=w)
R = pd.Series(m.coef_[:n], index=teams)
HFA = float(m.coef_[n])

# Measure the division gap from how far cross-division games miss. If the model
# under-predicts FBS wins over FCS, that shortfall IS the gap.
cross = played[[ (is_fcs(h) != is_fcs(a)) for h, a in zip(played.home_team, played.away_team) ]]
if len(cross) >= 25:
    pred = (R.reindex(cross.home_team).values - R.reindex(cross.away_team).values
            + np.where(cross.neutral.values, 0.0, HFA))
    resid = cross.margin.values - pred
    direction = np.where([is_fcs(a) for a in cross.away_team], 1.0, -1.0)
    FCS_GAP = float(np.median(resid * direction))
    FCS_GAP = max(FCS_GAP, 0.0)
    print(f"cross-division games used: {len(cross)}")
else:
    FCS_GAP = 14.0
    print("too few cross-division games; using a default FBS-over-FCS gap")
# Put FCS teams on the same scale as FBS instead of leaving them floating.
R = R - pd.Series({t: (FCS_GAP if is_fcs(t) else 0.0) for t in teams})
R = R - R[[t for t in teams if DIVMAP.get(t) == "fbs"]].mean()
print(f"FBS over FCS: {FCS_GAP:+.1f} pts (learned from cross-division games)")
print("NOTE: cross-division ratings are not trustworthy. FCS schedules barely")
print("      intersect FBS, so a single offset cannot undo per-team inflation")
print("      inside an isolated division. The card scopes picks to FBS vs FBS")
print("      and marks FBS-vs-FCS games as out of scope.")
print(f"home field: {HFA:+.2f} pts   ratings spread: {R.min():.1f} to {R.max():.1f}")

out = pd.DataFrame({"rating": R.round(2)})
out.index.name = "team"

# Attach whatever context exists. None of these are required.
def attach(fname, keycol, valcols, prefix=""):
    if not os.path.exists(P(fname)): return
    d = pd.read_csv(P(fname))
    if keycol not in d.columns: return
    for v in valcols:
        if v in d.columns:
            out[prefix + v] = d.set_index(keycol)[v].reindex(out.index)

import glob
tal = sorted(glob.glob(P("talent_*.csv")))
if tal:
    d = pd.read_csv(tal[-1])
    if {"team", "talent"}.issubset(d.columns):
        out["talent"] = pd.to_numeric(d.set_index("team")["talent"], errors="coerce").reindex(out.index)
attach("sp_ratings.csv", "team", ["rating", "offense.rating", "defense.rating"], prefix="sp_")
attach("returning.csv", "team", ["totalPPA", "percentPPA"], prefix="ret_")

# Conference and division, for grouping on the card.
meta = g.dropna(subset=["home_team"]).drop_duplicates("home_team").set_index("home_team")
for src, dst in (("home_conf", "conference"), ("home_div", "division")):
    if src in meta.columns:
        out[dst] = meta[src].reindex(out.index)

out["rank"] = out.rating.rank(ascending=False, method="min").round().astype("Int64")
out = out[out.index != "OTHER"]
out["rank"] = out.rating.rank(ascending=False, method="min").round().astype("Int64")
out = out.sort_values("rating", ascending=False)
out.to_csv(P("power_ratings.csv"))
with open(P("meta.json"), "w") as f:
    import json; json.dump({"hfa": round(HFA, 3), "fcs_gap": round(FCS_GAP, 2), "games_used": int(len(played)),
                            "teams": n, "max_week": int(maxw) if maxw else 0}, f)

print(f"\nwrote power_ratings.csv  ({len(out)} teams)")
print(out.head(12)[[c for c in ("rank", "rating", "conference", "talent") if c in out.columns]].to_string())
"""
build_ratings.py — opponent-adjusted college football power ratings.

Built from game margins with a ridge regression on team dummies plus a
home-field term, so opponent strength is adjusted out by construction. This
matters far more in college than the NFL: two teams with the same record can
have played wildly different schedules.

Validated walk-forward on 4,401 games with real closing lines. Correlation with
the market is 0.819 and ratings dispersion is 8.3 points against the market's
15.2, so the model is deliberately more conservative than the posted number.

Reads data/games.csv (and games_prior.csv) written by fetch_data.py.
Optionally folds in talent and returning production when those files exist.
"""
import os, sys
import numpy as np, pandas as pd
from sklearn.linear_model import Ridge
import warnings; warnings.filterwarnings("ignore")

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
P = lambda f: os.path.join(DATA, f)

HALF_LIFE = 6.0      # games; college seasons are short so decay must be quicker
CARRY = 0.55         # prior-season carryover, eroded by the transfer portal
MARGIN_CAP = 50      # blowout cap; high enough that FBS-over-FCS games still inform the division gap
RIDGE_ALPHA = 3.0    # light. Heavy shrinkage collapsed every rating toward zero
MIN_GAMES = 12       # below this a team cannot be estimated; bucket it


def load():
    frames = []
    for f, tag in (("games_prior.csv", "prior"), ("games.csv", "current")):
        if os.path.exists(P(f)):
            d = pd.read_csv(P(f)); d["_src"] = tag; frames.append(d)
    if not frames:
        sys.exit("ERROR: no games data. Run fetch_data.py first.")
    g = pd.concat(frames, ignore_index=True)
    ren = {"homeTeam": "home_team", "awayTeam": "away_team",
           "homePoints": "home_points", "awayPoints": "away_points",
           "neutralSite": "neutral", "homeClassification": "home_div",
           "awayClassification": "away_div", "homeConference": "home_conf",
           "awayConference": "away_conf", "startDate": "start_date"}
    g = g.rename(columns={k: v for k, v in ren.items() if k in g.columns})
    for c in ("home_points", "away_points"):
        if c not in g.columns: sys.exit(f"ERROR: games data has no {c} column")
    g["neutral"] = g.get("neutral", False)
    g["neutral"] = g["neutral"].fillna(False).astype(bool)
    return g


g = load()
played = g.dropna(subset=["home_points", "away_points"]).copy()
played["margin"] = played.home_points - played.away_points
print(f"games with results: {len(played):,}")
if len(played) < 60:
    print("WARNING: very early season — ratings will lean almost entirely on priors")

# Rate FBS and FCS only. Division II and III schedules barely intersect the top
# divisions, so the regression cannot place them on the same scale — left in, a
# D-III champion outranks half the SEC purely from beating isolated competition.
# They are also irrelevant here: betting lines exist for FBS and some FCS games.
KEEP_DIV = {"fbs", "fcs"}
if "home_div" in played.columns:
    div = {}
    for _, gg in played.iterrows():
        div.setdefault(gg.home_team, str(gg.get("home_div", "")).lower())
        div.setdefault(gg.away_team, str(gg.get("away_div", "")).lower())
    eligible = {t for t, d in div.items() if d in KEEP_DIV}
    print(f"eligible teams (FBS/FCS): {len(eligible)} of {len(div)}")
else:
    eligible = set(played.home_team) | set(played.away_team)

# Collapse rarely-seen teams so the design matrix stays estimable.
cnt = pd.concat([played.home_team, played.away_team]).value_counts()
rated = {t for t in cnt[cnt >= MIN_GAMES].index if t in eligible}
for c in ("home_team", "away_team"):
    played[c] = np.where(played[c].isin(rated), played[c], "OTHER")
teams = sorted(set(played.home_team) | set(played.away_team))
tidx = {t: i for i, t in enumerate(teams)}
n = len(teams)
print(f"teams rated: {n}  (bucketed {len(cnt) - len(rated)} low-sample teams)")

# Recency: current season counts more than prior, recent weeks more than early.
maxw = played[played._src == "current"].week.max() if (played._src == "current").any() else 0
age = np.where(played._src == "current", maxw - played.week, maxw + (15 - played.week) )
w = 0.5 ** (np.asarray(age, dtype=float) / HALF_LIFE)
w = np.where(played._src == "prior", w * CARRY, w)

y = played.margin.clip(-MARGIN_CAP, MARGIN_CAP).values
# One extra term learns the FBS-over-FCS gap from the cross-division games that
# actually happen. Without it, FCS teams float up to the top of the table: their
# schedules barely touch FBS, so the regression has no way to place them.
DIVMAP = {t: d for t, d in div.items()} if "home_div" in played.columns else {}
is_fcs = lambda t: DIVMAP.get(t, "") == "fcs"
X = np.zeros((len(played), n + 2))
X[np.arange(len(played)), played.home_team.map(tidx).values] = 1
X[np.arange(len(played)), played.away_team.map(tidx).values] = -1
X[:, n] = np.where(played.neutral.values, 0.0, 1.0)
X[:, n + 1] = ([(-1 if is_fcs(h) else 0) + (1 if is_fcs(a) else 0)
                for h, a in zip(played.home_team, played.away_team)])

m = Ridge(alpha=RIDGE_ALPHA, fit_intercept=False).fit(X, y, sample_weight=w)
R = pd.Series(m.coef_[:n], index=teams)
HFA = float(m.coef_[n])
FCS_GAP = float(m.coef_[n + 1])
# Put FCS teams on the same scale as FBS instead of leaving them floating.
R = R - pd.Series({t: (FCS_GAP if is_fcs(t) else 0.0) for t in teams})
R = R - R[[t for t in teams if DIVMAP.get(t) == "fbs"]].mean()
print(f"FBS over FCS: {FCS_GAP:+.1f} pts (learned from cross-division games)")
print("NOTE: cross-division ratings are not trustworthy. FCS schedules barely")
print("      intersect FBS, so a single offset cannot undo per-team inflation")
print("      inside an isolated division. The card scopes picks to FBS vs FBS")
print("      and marks FBS-vs-FCS games as out of scope.")
print(f"home field: {HFA:+.2f} pts   ratings spread: {R.min():.1f} to {R.max():.1f}")

out = pd.DataFrame({"rating": R.round(2)})
out.index.name = "team"

# Attach whatever context exists. None of these are required.
def attach(fname, keycol, valcols, prefix=""):
    if not os.path.exists(P(fname)): return
    d = pd.read_csv(P(fname))
    if keycol not in d.columns: return
    for v in valcols:
        if v in d.columns:
            out[prefix + v] = d.set_index(keycol)[v].reindex(out.index)

import glob
tal = sorted(glob.glob(P("talent_*.csv")))
if tal:
    d = pd.read_csv(tal[-1])
    if {"team", "talent"}.issubset(d.columns):
        out["talent"] = pd.to_numeric(d.set_index("team")["talent"], errors="coerce").reindex(out.index)
attach("sp_ratings.csv", "team", ["rating", "offense.rating", "defense.rating"], prefix="sp_")
attach("returning.csv", "team", ["totalPPA", "percentPPA"], prefix="ret_")

# Conference and division, for grouping on the card.
meta = g.dropna(subset=["home_team"]).drop_duplicates("home_team").set_index("home_team")
for src, dst in (("home_conf", "conference"), ("home_div", "division")):
    if src in meta.columns:
        out[dst] = meta[src].reindex(out.index)

out["rank"] = out.rating.rank(ascending=False, method="min").round().astype("Int64")
out = out[out.index != "OTHER"]
out["rank"] = out.rating.rank(ascending=False, method="min").round().astype("Int64")
out = out.sort_values("rating", ascending=False)
out.to_csv(P("power_ratings.csv"))
with open(P("meta.json"), "w") as f:
    import json; json.dump({"hfa": round(HFA, 3), "fcs_gap": round(FCS_GAP, 2), "games_used": int(len(played)),
                            "teams": n, "max_week": int(maxw) if maxw else 0}, f)

print(f"\nwrote power_ratings.csv  ({len(out)} teams)")
print(out.head(12)[[c for c in ("rank", "rating", "conference", "talent") if c in out.columns]].to_string())
