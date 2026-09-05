"""
cfb_backtest.py — does the college model actually beat the closing line?

This is the question the card cannot answer for itself. It replays five
seasons week by week, building the ratings from only what was known at the
time, prices every game, and compares the result against the real closing
number. Nothing here feeds the card. It exists to tell us whether the card's
disagreements with the market are worth anything.

It rebuilds the ratings exactly the way build_ratings.py does, including the
talent prior. If you change a constant there, change it here too, or the answer
stops applying to the model that is actually running. The constants are printed
at the top of every run so drift is visible.

The API key is read from the CFBD_API_KEY environment variable and sent in an
Authorization HEADER, never in a URL.

Run it from the Actions tab. It takes a few minutes and writes nothing to the
repo: the answer is the log.
"""
import os, sys, time
import numpy as np, pandas as pd
import requests
from sklearn.linear_model import Ridge
import warnings; warnings.filterwarnings("ignore")

# ---- these must match build_ratings.py ----
HALF_LIFE = 6.0
CARRY = 0.55
MARGIN_CAP = 50
RIDGE_ALPHA = 1.5
MIN_GAMES = 12
TALENT_PTS = 8.0
TALENT_CAP = 2.5
# ---- backtest-only ----
SEASONS = [2021, 2022, 2023, 2024, 2025]
TEST = [2022, 2023, 2024, 2025]      # 2021 is priors only
BREAK_EVEN = 52.4                     # at -110

API = "https://api.collegefootballdata.com"
KEY = os.environ.get("CFBD_API_KEY", "").strip()
if not KEY:
    sys.exit("ERROR: CFBD_API_KEY is not set. Add it under Settings > Secrets and variables > Actions")
SESSION = requests.Session()
SESSION.headers.update({"Authorization": f"Bearer {KEY}", "Accept": "application/json"})


def get(path, **params):
    for attempt in range(4):
        try:
            r = SESSION.get(f"{API}{path}", params=params, timeout=40)
        except requests.RequestException as e:
            print(f"  network error on {path}: {e}"); time.sleep(3 * (attempt + 1)); continue
        if r.status_code == 200:
            return r.json()
        if r.status_code in (401, 403):
            sys.exit(f"ERROR: CFBD rejected the key on {path} (HTTP {r.status_code}).")
        if r.status_code == 429:
            print(f"  rate limited on {path}, waiting"); time.sleep(10 * (attempt + 1)); continue
        print(f"  HTTP {r.status_code} on {path}"); time.sleep(2 * (attempt + 1))
    return None


print("constants in use:")
print(f"  half-life {HALF_LIFE}   carry {CARRY}   ridge alpha {RIDGE_ALPHA}")
print(f"  talent {TALENT_PTS} pts per sd, clipped at {TALENT_CAP}   margin cap {MARGIN_CAP}")
print()

# ---------------- load ----------------
games, talent = [], {}
for yr in SEASONS:
    g = get("/games", year=yr, seasonType="regular")
    if not g:
        sys.exit(f"ERROR: no games came back for {yr}")
    d = pd.json_normalize(g); d["season"] = yr
    games.append(d)
    t = get("/talent", year=yr)
    if t:
        td = pd.json_normalize(t)
        if {"team", "talent"}.issubset(td.columns):
            talent[yr] = pd.to_numeric(td.set_index("team")["talent"], errors="coerce").dropna()
    print(f"  {yr}: {len(d):,} games, talent for {len(talent.get(yr, [])):,} teams")

G = pd.concat(games, ignore_index=True).rename(columns={
    "homeTeam": "home_team", "awayTeam": "away_team", "homePoints": "home_points",
    "awayPoints": "away_points", "neutralSite": "neutral",
    "homeClassification": "home_div", "awayClassification": "away_div"})
G["neutral"] = G["neutral"].fillna(False).astype(bool)
G = G.dropna(subset=["home_points", "away_points"]).copy()
G["margin"] = G.home_points - G.away_points
G["total"] = G.home_points + G.away_points
print(f"\ncompleted games loaded: {len(G):,}")

DIV = {}
for _, r in G.iterrows():
    DIV.setdefault(r.home_team, str(r.home_div).lower())
    DIV.setdefault(r.away_team, str(r.away_div).lower())
is_fbs = lambda t: DIV.get(t, "") == "fbs"
is_fcs = lambda t: DIV.get(t, "") == "fcs"

# ---------------- lines ----------------
rows = []
for yr in TEST:
    L = get("/lines", year=yr, seasonType="regular")
    if not L:
        print(f"  WARNING: no lines for {yr}")
        continue
    for game in L:
        bl = game.get("lines") or []
        sp = [b.get("spread") for b in bl if b.get("spread") is not None]
        ou = [b.get("overUnder") for b in bl if b.get("overUnder") is not None]
        hm = [b.get("homeMoneyline") for b in bl if b.get("homeMoneyline") is not None]
        if not sp:
            continue
        rows.append(dict(season=yr, week=game.get("week"),
                         home_team=game.get("homeTeam"), away_team=game.get("awayTeam"),
                         mkt_spread=float(np.median(sp)),
                         mkt_total=float(np.median(ou)) if ou else np.nan,
                         mkt_home_ml=float(np.median(hm)) if hm else np.nan,
                         books=len(sp)))
    print(f"  {yr}: {sum(1 for r in rows if r['season'] == yr):,} games with a spread")
LINES = pd.DataFrame(rows)
if LINES.empty:
    sys.exit("ERROR: no betting lines came back. Nothing to grade against.")

# ---------------- ratings, rebuilt as of a point in time ----------------
cnt = pd.concat([G.home_team, G.away_team]).value_counts()
ELIGIBLE = {t for t, d in DIV.items() if d in ("fbs", "fcs")}
RATED = {t for t in cnt[cnt >= MIN_GAMES].index if t in ELIGIBLE}
GB = G.copy()
for c in ("home_team", "away_team"):
    GB[c] = np.where(GB[c].isin(RATED), GB[c], "OTHER")
TEAMS = sorted(set(GB.home_team) | set(GB.away_team))
TIDX = {t: i for i, t in enumerate(TEAMS)}
NT = len(TEAMS)
print(f"teams rated: {NT}")


def talent_prior(season):
    """Talent as of that season only. Zero for FCS and for the OTHER bucket, so
    the prior carries no division information."""
    tal = talent.get(season)
    if tal is None or len(tal) < 40:
        return pd.Series(0.0, index=TEAMS)
    fbs_tal = tal[[t for t in tal.index if is_fbs(t)]]
    if len(fbs_tal) < 40:
        return pd.Series(0.0, index=TEAMS)
    z = ((tal - fbs_tal.mean()) / fbs_tal.std()).clip(-TALENT_CAP, TALENT_CAP)
    return pd.Series({t: (TALENT_PTS * z[t] if (is_fbs(t) and t in z.index) else 0.0)
                      for t in TEAMS})


def fit_as_of(season, week, use_talent=True):
    """Everything known before (season, week): the prior season plus this
    season's earlier weeks. Mirrors build_ratings.py."""
    hist = GB[((GB.season == season - 1)) | ((GB.season == season) & (GB.week < week))]
    if len(hist) < 200:
        return None, None, None
    maxw = week - 1
    src_current = (hist.season == season).values
    age = np.where(src_current, maxw - hist.week.values, maxw + (15 - hist.week.values))
    w = 0.5 ** (age.astype(float) / HALF_LIFE)
    w = np.where(src_current, w, w * CARRY)
    prior = talent_prior(season) if use_talent else pd.Series(0.0, index=TEAMS)
    X = np.zeros((len(hist), NT + 1))
    X[np.arange(len(hist)), hist.home_team.map(TIDX).values] = 1
    X[np.arange(len(hist)), hist.away_team.map(TIDX).values] = -1
    X[:, NT] = np.where(hist.neutral.values, 0.0, 1.0)
    ph = prior.reindex(hist.home_team).values
    pa = prior.reindex(hist.away_team).values
    y = hist.margin.clip(-MARGIN_CAP, MARGIN_CAP).values
    m = Ridge(alpha=RIDGE_ALPHA, fit_intercept=False).fit(X, y - (ph - pa), sample_weight=w)
    R = prior + pd.Series(m.coef_[:NT], index=TEAMS)
    hfa = float(m.coef_[NT])
    # cross-division gap: one side FBS, the other FCS, and nothing else
    cross = hist[[(is_fbs(h) and is_fcs(a)) or (is_fcs(h) and is_fbs(a))
                  for h, a in zip(hist.home_team, hist.away_team)]]
    gap = 14.0
    if len(cross) >= 25:
        pred = (R.reindex(cross.home_team).values - R.reindex(cross.away_team).values
                + np.where(cross.neutral.values, 0.0, hfa))
        d = cross.margin.values - pred
        direction = np.where([is_fcs(a) for a in cross.away_team], 1.0, -1.0)
        gap = max(float(np.median(d * direction)), 0.0)
    R = R - pd.Series({t: (gap if is_fcs(t) else 0.0) for t in TEAMS})
    R = R - R[[t for t in TEAMS if is_fbs(t)]].mean()
    return R, hfa, gap


def price(use_talent):
    out = []
    for season in TEST:
        for week in sorted(GB[GB.season == season].week.unique()):
            R, hfa, gap = fit_as_of(season, week, use_talent)
            if R is None:
                continue
            cur = GB[(GB.season == season) & (GB.week == week)]
            for _, gg in cur.iterrows():
                if gg.home_team == "OTHER" or gg.away_team == "OTHER":
                    continue
                out.append(dict(season=season, week=week,
                                home_team=gg.home_team, away_team=gg.away_team,
                                model=float(R[gg.home_team] - R[gg.away_team]
                                            + (0.0 if gg.neutral else hfa)),
                                margin=gg.margin, total=gg.total,
                                fbs=(is_fbs(gg.home_team) and is_fbs(gg.away_team))))
        print(f"  {season} priced ({'with' if use_talent else 'without'} talent)")
    return pd.DataFrame(out)


def grade(B, label):
    """ATS record by how far the model is from the market."""
    B = B.dropna(subset=["mkt_spread"]).copy()
    # market's implied home margin is the negative of the posted home spread
    B["mkt_margin"] = -B.mkt_spread
    B["edge"] = B.model - B.mkt_margin
    B["push"] = B.margin == B.mkt_margin
    B = B[~B.push]
    if len(B) < 50:
        print(f"\n{label}: too few games to say anything"); return
    home_covers = B.margin > B.mkt_margin
    picked_home = B.edge > 0
    win = (picked_home & home_covers) | (~picked_home & ~home_covers)
    print(f"\n{label}   (n={len(B):,})")
    print(f"  {'min edge':>9} {'games':>7} {'record':>13} {'win%':>8}")
    for lo, hi in ((0, 99), (0, 3), (3, 6), (6, 10), (10, 14), (14, 99)):
        m = (B.edge.abs() >= lo) & (B.edge.abs() < hi)
        if m.sum() < 40:
            continue
        wins = int(win[m].sum()); losses = int(m.sum() - wins)
        pct = 100 * wins / max(wins + losses, 1)
        band = f"{lo} to {hi}" if hi < 99 else f"{lo}+"
        flag = "  beats break-even" if pct > BREAK_EVEN else ""
        print(f"  {band:>9} {int(m.sum()):>7} {f'{wins}-{losses}':>13} {pct:>7.1f}%{flag}")


def grade_totals(B, label):
    B = B.dropna(subset=["mkt_total"]).copy()
    B = B[B.total != B.mkt_total]
    if len(B) < 50:
        print(f"\n{label}: too few games"); return
    print(f"\n{label}   (n={len(B):,})")
    print("  (totals are graded on the market number only, since the model's")
    print("   own totals model is not part of the ratings)")
    over = B.total > B.mkt_total
    print(f"  overs hit {100*over.mean():.1f}% of the time, so the market total is roughly fair")


def diagnostics(B, label):
    B = B.dropna(subset=["mkt_spread"]).copy()
    B["mkt_margin"] = -B.mkt_spread
    print(f"\n{label}")
    print(f"  model vs market correlation : {np.corrcoef(B.model, B.mkt_margin)[0,1]:.3f}")
    print(f"  model spread sd {B.model.std():.2f}   market spread sd {B.mkt_margin.std():.2f}")
    print(f"  market MAE vs actual margin : {(B.mkt_margin - B.margin).abs().mean():.2f}")
    print(f"  model  MAE vs actual margin : {(B.model - B.margin).abs().mean():.2f}")
    sl = np.polyfit(B.model, B.margin, 1)[0]
    print(f"  actual = {sl:.3f} x model   (1.00 means the model's scale is right)")


print("\npricing every week from the ratings that existed at the time")
WITH = price(True).merge(LINES, on=["season", "week", "home_team", "away_team"], how="inner")
WITHOUT = price(False).merge(LINES, on=["season", "week", "home_team", "away_team"], how="inner")
print(f"\ngames matched to a closing line: with talent {len(WITH):,}, without {len(WITHOUT):,}")

print("\n" + "=" * 70)
print("SPREAD RESULTS   (break-even at -110 is 52.4%)")
print("=" * 70)
grade(WITH[WITH.fbs], "WITH the talent anchor, FBS vs FBS")
grade(WITHOUT[WITHOUT.fbs], "WITHOUT the talent anchor, FBS vs FBS (the old model)")
grade(WITH, "WITH the talent anchor, every game including cross-division")
for y in TEST:
    grade(WITH[(WITH.season == y) & WITH.fbs], f"{y} only, FBS vs FBS, with talent")

print("\n" + "=" * 70)
print("DIAGNOSTICS")
print("=" * 70)
diagnostics(WITH[WITH.fbs], "with the talent anchor, FBS vs FBS")
diagnostics(WITHOUT[WITHOUT.fbs], "without it")
grade_totals(WITH[WITH.fbs], "totals sanity check, FBS vs FBS")

print("\n" + "=" * 70)
print("WHAT THIS MEANS")
print("=" * 70)
print("Read the win% column against 52.4%. A number below it means betting the")
print("model's disagreements loses money at standard juice, however large the")
print("disagreement looks. If win% falls as the edge band rises, the model is")
print("not finding mispriced games, it is being wrong in a way the market is not.")
print("Small samples swing several points on luck alone: a 500-game bucket has a")
print("standard error of about 2.2 points, so treat anything inside 52.4 plus or")
print("minus 4 as no evidence either way.")
