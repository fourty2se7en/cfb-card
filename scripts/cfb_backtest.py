"""
cfb_backtest.py — what, if anything, can this project honestly bet?

Version 1 asked one question: does the model beat the CLOSING line? The answer
was no. 50.3% over 2,789 FBS-vs-FBS games against a 52.4% break-even, getting
worse as the disagreement grew.

That question is not the only one. This version tests five, because a model can
fail against the close and still be worth something, and because two of these
strategies do not depend on the model at all:

  1. Against the CLOSING line. The version 1 question, kept as the baseline.
  2. Against the OPENING line. Books open soft and sharpen through the week. A
     model that cannot beat the closing number can still beat the opener.
  3. Closing line value. When we disagree with the opener, does the line move
     TOWARD us? This is the single best evidence that a model sees something
     real, because it is measured before any game is played.
  4. Price consistency. A book's own moneyline, de-vigged, converted to a
     spread and compared with that same book's posted spread. When they
     disagree one is stale. This needs no model at all.
  5. Subgroups, because 5.8 says a smaller market is where an edge would live:
     G5 against G5, games where SP+ agrees with us, and early versus late.

Whatever clears 52.4% here is what the card is allowed to call a pick. Nothing
else is.

It rebuilds the ratings exactly the way build_ratings.py does, including the
talent prior. Both read their constants from model_state.json, so the two
cannot drift apart: change a value there and this test and the live model move
together. The constants are printed at the top of every run.

What this run finds is written back into model_state.json, which is where
cfb_picks.py reads the records that set every grade and where cfb_card.py reads
the figures it quotes. There is nothing to paste afterwards.

The API key is read from the CFBD_API_KEY environment variable and sent in an
Authorization HEADER, never in a URL.

Run it from the Actions tab. The answer is written to the run's Summary page.
"""
import os, sys, time
import numpy as np, pandas as pd
import requests
from sklearn.linear_model import Ridge
import cfb_fit as FIT
from scipy.stats import norm
from scipy.optimize import minimize
import warnings; warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model_state as MS

# Every constant below is read from model_state.json, the same copy
# build_ratings.py and cfb_card.py read. They used to be typed here a second
# time under a comment saying they must match, which is a rule a person has to
# keep rather than one the code keeps.
HALF_LIFE = float(MS.RATINGS["half_life"])
CARRY = float(MS.RATINGS["carry"])
MARGIN_CAP = float(MS.RATINGS["margin_cap"])
RIDGE_ALPHA = float(MS.RATINGS["ridge_alpha"])
MIN_GAMES = int(MS.RATINGS["min_games"])
TALENT_PTS = float(MS.RATINGS["talent_pts"])
TALENT_CAP = float(MS.RATINGS["talent_cap"])
GAME_SD = float(MS.TH["game_sd"])
PRICE_FLAG = float(MS.TH["price_flag"])
PRICE_MAX = float(MS.TH["price_max"])
ML_SANE = float(MS.TH["ml_sane"])
SPPLUS_FLAG = float(MS.TH["spplus_flag"])
BREAK_EVEN = float(MS.TH["break_even"])
TOTAL_ALPHA = float(MS.TOTALS["alpha"])
TOTAL_CAP = float(MS.TOTALS["cap"])
if MS.FELL_BACK:
    sys.exit(f"ERROR: {MS.FELL_BACK}. This will not run on guessed constants, because "
             f"its whole job is to say what the live model does. Fix "
             f"scripts/model_state.json and run it again.")
# ---- backtest-only ----
# 2017 is the start of the transfer portal era. Earlier college football is
# close enough to a different sport that pooling it can mislead rather than
# help, and betting line coverage thins out. The run reports the older half
# against the newer half so the assumption is checked rather than trusted.
SEASONS = list(range(2016, 2026))
TEST = list(range(2017, 2026))

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


def wilson(wins, n):
    """95% interval on a win rate, so a lucky bucket cannot masquerade as edge."""
    if n == 0:
        return 0.0, 0.0
    p = wins / n
    z = 1.96
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return 100 * (c - m), 100 * (c + m)


def verdict(wins, losses):
    n = wins + losses
    if n < 100:
        return "too few games to say"
    lo, hi = wilson(wins, n)
    if lo > BREAK_EVEN:
        return f"CLEARS break-even ({lo:.1f} to {hi:.1f} at 95%)"
    if hi < BREAK_EVEN:
        return f"loses at -110 ({lo:.1f} to {hi:.1f} at 95%)"
    return f"no evidence either way ({lo:.1f} to {hi:.1f} at 95%)"


def report(mask, win, label, sub):
    n = int(mask.sum())
    if n < 40:
        return
    w = int(win[mask].sum()); l = n - w
    pct = 100 * w / max(n, 1)
    print(f"  {label:<22} {n:>6} {f'{w}-{l}':>13} {pct:>7.1f}%   {verdict(w, l)}")


print("constants in use:")
print(f"  half-life {HALF_LIFE}  carry {CARRY}  ridge alpha {RIDGE_ALPHA}  talent {TALENT_PTS}")
print(f"  price flag {PRICE_FLAG} inside {PRICE_MAX} points, game sd {GAME_SD}")
print()

# ---------------- load ----------------
games, talent, returning, ppa = [], {}, {}, {}
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
    # Returning production. Section 4.4 calls roster turnover the leading known
    # defect, and 4.5a says to test it as a Week-1 shrinkage term. That cannot be
    # tested without the historical figures, which nothing here fetched before.
    rp = get("/player/returning", year=yr)
    if rp:
        rd = pd.json_normalize(rp)
        if {"team", "percentPPA"}.issubset(rd.columns):
            returning[yr] = pd.to_numeric(rd.set_index("team")["percentPPA"],
                                          errors="coerce").dropna()
    # Per-play efficiency. Section 5.1 says the NFL card rates on play-by-play
    # efficiency and the college one on game margins, because college play-by-play
    # is not freely available. PPA is the part of it that IS available: one number
    # per team per game for how much each play was worth. Garbage time is excluded,
    # which is most of the reason to prefer efficiency to the scoreboard.
    pp = get("/ppa/games", year=yr, seasonType="regular", excludeGarbageTime="true")
    if pp:
        pd_ = pd.json_normalize(pp)
        off = next((c for c in ("offense.overall", "off_overall") if c in pd_.columns), None)
        dfn = next((c for c in ("defense.overall", "def_overall") if c in pd_.columns), None)
        gid = next((c for c in ("gameId", "game_id", "id") if c in pd_.columns), None)
        if off and gid and "team" in pd_.columns:
            pd_ = pd_.rename(columns={off: "off", gid: "gid"})
            _keep = pd_[["gid", "team", "off"] + ([dfn] if dfn else [])].rename(
                columns={dfn: "dfn"} if dfn else {})
            _keep["gid"] = pd.to_numeric(_keep["gid"], errors="coerce")
            _keep["off"] = pd.to_numeric(_keep["off"], errors="coerce")
            _keep["dfn"] = (pd.to_numeric(_keep["dfn"], errors="coerce")
                            if "dfn" in _keep.columns else np.nan)
            ppa[yr] = _keep.dropna(subset=["gid", "team"])
    print(f"  {yr}: {len(d):,} games, talent for {len(talent.get(yr, [])):,} teams, "
          f"returning production for {len(returning.get(yr, [])):,}, "
          f"per-play efficiency rows {len(ppa.get(yr, [])):,}")

G = pd.concat(games, ignore_index=True).rename(columns={
    "homeTeam": "home_team", "awayTeam": "away_team", "homePoints": "home_points",
    "awayPoints": "away_points", "neutralSite": "neutral",
    "homeClassification": "home_div", "awayClassification": "away_div",
    "homeConference": "home_conf", "awayConference": "away_conf"})
G["neutral"] = G["neutral"].fillna(False).astype(bool)
G = G.dropna(subset=["home_points", "away_points"]).copy()
G["margin"] = G.home_points - G.away_points
G["total"] = G.home_points + G.away_points
print(f"\ncompleted games loaded: {len(G):,}")

# The per-game efficiency edge, on the same sign convention as margin: positive
# means the home side was the more efficient one. Built from the home and away
# offences in that game. If one side's offensive figure is missing, the same
# quantity is recovered from the defensive figures, which measure the same plays
# from the other side of the ball. Games with neither stay NaN and are simply
# fitted on their margin, as they always were.
def efficiency_edge(frame, by_season):
    """Home minus away per-play efficiency, one number per game.

    Kept in a function on purpose. Names bound in a long module-level block have
    silently clobbered module-level helpers in this file twice, and both times
    the run went green with a whole section quietly missing. See 4.3.
    """
    out = np.full(len(frame), np.nan)
    if not by_season:
        return out
    look = pd.concat(by_season.values(), ignore_index=True)
    gcol = next((c for c in ("id", "gameId", "game_id") if c in frame.columns), None)
    if gcol is None or look.empty:
        return out
    omap = look.set_index(["gid", "team"])["off"].to_dict()
    dmap = look.set_index(["gid", "team"])["dfn"].to_dict()
    gids = pd.to_numeric(frame[gcol], errors="coerce").values
    fin = lambda v: v is not None and np.isfinite(v)
    for i, (gi, h_, a_) in enumerate(zip(gids, frame.home_team.values,
                                         frame.away_team.values)):
        ho, ao = omap.get((gi, h_)), omap.get((gi, a_))
        if fin(ho) and fin(ao):
            out[i] = ho - ao
            continue
        # the defensive figures describe the same plays from the other side, so
        # they recover the same quantity when an offensive one is missing
        hd, ad = dmap.get((gi, h_)), dmap.get((gi, a_))
        if fin(hd) and fin(ad):
            out[i] = ad - hd
    return out


G["eff"] = efficiency_edge(G, ppa)
if ppa:
    _have = int(np.isfinite(G.eff.values).sum())
    print(f"games with a per-play efficiency edge: {_have:,} of {len(G):,} "
          f"({100 * _have / max(len(G), 1):.0f}%)")
else:
    print("no per-play efficiency came back; the efficiency test will be skipped")

DIV, CONF = {}, {}
for _, r in G.iterrows():
    DIV.setdefault(r.home_team, str(r.home_div).lower())
    DIV.setdefault(r.away_team, str(r.away_div).lower())
    CONF.setdefault(r.home_team, str(r.get("home_conf", "")))
    CONF.setdefault(r.away_team, str(r.get("away_conf", "")))
is_fbs = lambda t: DIV.get(t, "") == "fbs"
is_fcs = lambda t: DIV.get(t, "") == "fcs"
P4 = {"SEC", "Big Ten", "Big 12", "ACC", "Pac-12", "FBS Independents"}
is_p4 = lambda t: CONF.get(t, "") in P4

# ---------------- lines, close and open, per book ----------------
rows, bookrows = [], []
for yr in TEST:
    L = get("/lines", year=yr, seasonType="regular")
    if not L:
        print(f"  WARNING: no lines for {yr}")
        continue
    for game in L:
        bl = game.get("lines") or []
        key = dict(season=yr, week=game.get("week"),
                   home_team=game.get("homeTeam"), away_team=game.get("awayTeam"))
        sp = [b.get("spread") for b in bl if b.get("spread") is not None]
        op = [b.get("spreadOpen") for b in bl if b.get("spreadOpen") is not None]
        ou = [b.get("overUnder") for b in bl if b.get("overUnder") is not None]
        ouo = [b.get("overUnderOpen") for b in bl if b.get("overUnderOpen") is not None]
        if not sp:
            continue
        rows.append(dict(**key, close=float(np.median(sp)),
                         open=float(np.median(op)) if op else np.nan,
                         total_close=float(np.median(ou)) if ou else np.nan,
                         total_open=float(np.median(ouo)) if ouo else np.nan))
        for b in bl:
            s, h, a = b.get("spread"), b.get("homeMoneyline"), b.get("awayMoneyline")
            if s is None or h is None or a is None:
                continue
            if abs(h) > ML_SANE or abs(a) > ML_SANE or (h < 0 and a < 0) or (h > 0 and a > 0):
                continue
            bookrows.append(dict(**key, book=str(b.get("provider", "")), spread=float(s),
                                 hml=float(h), aml=float(a)))
    print(f"  {yr}: {sum(1 for r in rows if r['season'] == yr):,} games with a spread")
LINES = pd.DataFrame(rows)
BOOKS = pd.DataFrame(bookrows)
if LINES.empty:
    sys.exit("ERROR: no betting lines came back. Nothing to grade against.")
print(f"per-book quotes with a two-sided moneyline: {len(BOOKS):,}")

# ---------------- ratings as of a point in time ----------------
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
    tal = talent.get(season)
    if tal is None or len(tal) < 40:
        return pd.Series(0.0, index=TEAMS)
    fbs_tal = tal[[t for t in tal.index if is_fbs(t)]]
    if len(fbs_tal) < 40:
        return pd.Series(0.0, index=TEAMS)
    z = ((tal - fbs_tal.mean()) / fbs_tal.std()).clip(-TALENT_CAP, TALENT_CAP)
    return pd.Series({t: (TALENT_PTS * z[t] if (is_fbs(t) and t in z.index) else 0.0)
                      for t in TEAMS})


def ret_scale(season, strength, fade_games, counts=None):
    """Per-team column scaling, so a team that lost its roster is pulled harder
    toward what recruiting says.

    Ridge minimises ||y - Xb||^2 + a||b||^2. Scale column j by s_j and the fitted
    coefficient c_j satisfies b_j = s_j c_j, so the penalty a||c||^2 is
    a * sum (b_j / s_j)^2. A smaller s_j is therefore a LARGER penalty on that
    one team, which is exactly "shrink this team harder toward its prior" without
    touching anyone else. No new column, no division information, and nothing
    that ridge can split arbitrarily between teams. See 4.3a for why that matters.

    s_j = 1 - strength * (1 - ret_j) * fade_j
      ret_j   fraction of last season's production returning, 0 to 1
      fade_j  1 with no games played this season, falling to 0 once the team has
              fade_games of its own. That is the Week-1 part of 4.5a: a dozen
              real games should wash the prior out, and this makes it.
    Teams with no returning figure get the FBS median, so an unknown team is
    treated as ordinary rather than punished.
    """
    if strength <= 0:
        return np.ones(NT + 1)
    ret = returning.get(season)
    if ret is None or len(ret) < 40:
        return np.ones(NT + 1)
    med = float(ret.median())
    s = np.ones(NT + 1)
    for t, j in TIDX.items():
        r = float(ret.get(t, med))
        if not np.isfinite(r):
            r = med
        r = min(max(r, 0.0), 1.0)
        g = 0.0 if counts is None else float(counts.get(t, 0.0))
        fade = 1.0 if fade_games <= 0 else max(0.0, 1.0 - g / fade_games)
        s[j] = 1.0 - strength * (1.0 - r) * fade
    # never let a team be scaled to nothing: that would erase its games entirely
    s[:NT] = np.clip(s[:NT], 0.25, 1.0)
    s[NT] = 1.0            # home field is not a team and is never rescaled
    return s


def fit_as_of(season, week, ret_strength=0.0, ret_fade=0.0, ppa_weight=0.0):
    """The card's ratings, refitted from history only, as of this point in time.

    The fit itself is cfb_fit.fit_ratings, the same function build_ratings.py
    uses to produce the published ratings. It used to be written out again here,
    and the two copies had drifted: this one had the roster-turnover switch and
    the live model did not. Sharing it is what stops this file measuring a model
    that is not the one running. See section 2 and 4.3h.
    """
    hist = GB[(GB.season == season - 1) | ((GB.season == season) & (GB.week < week))]
    if len(hist) < 200:
        return None, None
    w = FIT.recency_weights((hist.season == season).values, hist.week.values,
                            week - 1, HALF_LIFE, CARRY)
    cur_hist = hist[hist.season == season]
    counts = (pd.concat([cur_hist.home_team, cur_hist.away_team]).value_counts()
              if len(cur_hist) else None)
    # The efficiency switch. At weight 0 the target is the margin and this is
    # byte-for-byte the model the card publishes. Above 0 the fit is asked to
    # explain a blend of the scoreboard and what per-play efficiency predicted
    # the scoreboard should have been.
    #
    # The points-per-unit-of-efficiency conversion is FITTED, on this history
    # only, and never carried in from anywhere. Section 6 exists because an NFL
    # constant was once reused here without measuring it. It is refitted at every
    # point in time, so nothing from the future reaches the number.
    _target = None
    if ppa_weight > 0 and "eff" in hist.columns:
        _e = hist.eff.values.astype(float)
        _m = hist.margin.values.astype(float)
        _ok = np.isfinite(_e) & np.isfinite(_m)
        if int(_ok.sum()) >= 200:
            _sw = np.sqrt(np.asarray(w, dtype=float)[_ok])
            _A = np.column_stack([np.ones(int(_ok.sum())), _e[_ok]])
            _co, *_ = np.linalg.lstsq(_A * _sw[:, None], _m[_ok] * _sw, rcond=None)
            _pred = _co[0] + _co[1] * _e
            _target = np.where(np.isfinite(_pred),
                               (1.0 - ppa_weight) * _m + ppa_weight * _pred, _m)
    out = FIT.fit_ratings(hist, TEAMS, TIDX, talent_prior(season), weights=w,
                          ridge_alpha=RIDGE_ALPHA, margin_cap=MARGIN_CAP,
                          is_fbs=is_fbs, is_fcs=is_fcs,
                          col_scale=ret_scale(season, ret_strength, ret_fade, counts),
                          target=_target)
    return out["rating"], out["hfa"]


def fit_totals_as_of(season, week):
    """The card's points model, refitted from history only.

    One row per team per game, so each team gets an offensive and a defensive
    points rating, exactly as cfb_card.py builds it. Without this the backtest
    had no model total at all, which is why totals could only ever be tested as
    "bet every over" and confidence on totals could not be calibrated.
    """
    hist = GB[(GB.season == season - 1) | ((GB.season == season) & (GB.week < week))]
    hist = hist.dropna(subset=["home_points", "away_points"])
    if len(hist) < 200:
        return None
    maxw = week - 1
    cur = (hist.season == season).values
    age = np.where(cur, maxw - hist.week.values, maxw + (15 - hist.week.values))
    w = 0.5 ** (age.astype(float) / HALF_LIFE)
    w = np.where(cur, w, w * CARRY)
    m2 = len(hist) * 2
    X = np.zeros((m2, 2 * NT + 1)); y = np.zeros(m2); ww = np.zeros(m2)
    hi = hist.home_team.map(TIDX).values; ai = hist.away_team.map(TIDX).values
    nz = np.where(hist.neutral.values, 0.0, 1.0)
    r = np.arange(len(hist))
    X[r, hi] = 1; X[r, NT + ai] = 1; X[r, 2 * NT] = nz
    y[r] = hist.home_points.clip(0, TOTAL_CAP).values; ww[r] = w
    r2 = r + len(hist)
    X[r2, ai] = 1; X[r2, NT + hi] = 1
    y[r2] = hist.away_points.clip(0, TOTAL_CAP).values; ww[r2] = w
    mdl = Ridge(alpha=TOTAL_ALPHA, fit_intercept=True).fit(X, y, sample_weight=ww)
    return (pd.Series(mdl.coef_[:NT], index=TEAMS),
            pd.Series(mdl.coef_[NT:2 * NT], index=TEAMS),
            float(mdl.coef_[2 * NT]), float(mdl.intercept_))


out = []
for season in TEST:
    for week in sorted(GB[GB.season == season].week.unique()):
        R, hfa = fit_as_of(season, week)
        if R is None:
            continue
        T = fit_totals_as_of(season, week)
        cur = GB[(GB.season == season) & (GB.week == week)]
        for _, gg in cur.iterrows():
            if gg.home_team == "OTHER" or gg.away_team == "OTHER":
                continue
            out.append(dict(season=season, week=week, home_team=gg.home_team,
                            away_team=gg.away_team,
                            model=float(R[gg.home_team] - R[gg.away_team]
                                        + (0.0 if gg.neutral else hfa)),
                            margin=gg.margin, total=gg.total,
                            model_total=(None if T is None else
                                         float(2 * T[3] + T[0][gg.home_team] + T[1][gg.away_team]
                                               + T[0][gg.away_team] + T[1][gg.home_team]
                                               + (0.0 if gg.neutral else T[2]))),
                            fbs=(is_fbs(gg.home_team) and is_fbs(gg.away_team)),
                            g5=(is_fbs(gg.home_team) and is_fbs(gg.away_team)
                                and not is_p4(gg.home_team) and not is_p4(gg.away_team))))
    print(f"  {season} priced")

M = pd.DataFrame(out).merge(LINES, on=["season", "week", "home_team", "away_team"], how="inner")
M["mkt_close"] = -M["close"]                 # implied home margin
M["mkt_open"] = -M["open"]
F = M[M.fbs].copy()
print(f"\ngames matched to a line: {len(M):,}   FBS vs FBS: {len(F):,}"
      f"   with an opening number: {int(F.mkt_open.notna().sum()):,}")

print("\n" + "=" * 78)
print("TEST 1 — AGAINST THE CLOSING LINE   (break-even 52.4%)")
print("=" * 78)
d = F[F.margin != F.mkt_close].copy()
d["edge"] = d.model - d.mkt_close
covers = d.margin > d.mkt_close
win1 = ((d.edge > 0) & covers) | ((d.edge <= 0) & ~covers)
print(f"  {'disagreement':<22} {'games':>6} {'record':>13} {'win%':>8}   verdict")
for lo, hi, lab in ((0, 99, "any"), (0, 3, "0 to 3"), (3, 6, "3 to 6"),
                    (6, 10, "6 to 10"), (10, 99, "10 or more")):
    report((d.edge.abs() >= lo) & (d.edge.abs() < hi), win1, lab, d)

print("\n" + "=" * 78)
print("TEST 2 — AGAINST THE OPENING LINE")
print("=" * 78)
o = F[F.mkt_open.notna() & (F.margin != F.mkt_open)].copy()
if len(o) < 100:
    print("  not enough opening lines came back to test this")
else:
    o["edge"] = o.model - o.mkt_open
    ocov = o.margin > o.mkt_open
    win2 = ((o.edge > 0) & ocov) | ((o.edge <= 0) & ~ocov)
    print(f"  {'disagreement':<22} {'games':>6} {'record':>13} {'win%':>8}   verdict")
    for lo, hi, lab in ((0, 99, "any"), (0, 3, "0 to 3"), (3, 6, "3 to 6"),
                        (6, 10, "6 to 10"), (10, 99, "10 or more")):
        report((o.edge.abs() >= lo) & (o.edge.abs() < hi), win2, lab, o)

print("\n" + "=" * 78)
print("TEST 3 — CLOSING LINE VALUE. Does the line move toward our number?")
print("=" * 78)
c = F[F.mkt_open.notna()].copy()
if len(c) < 100:
    print("  not enough opening lines to test this")
else:
    c["edge_open"] = c.model - c.mkt_open
    c["move"] = c.mkt_close - c.mkt_open
    moved = c[c.move != 0]
    r = np.corrcoef(c.edge_open, c.move)[0, 1]
    print(f"  games with an opener: {len(c):,}   of those the line moved in {len(moved):,}")
    print(f"  correlation between our disagreement and the move: {r:+.3f}")
    print(f"  (a positive number means the market drifts toward us before kickoff)")
    for lo in (0, 3, 6, 10):
        s = moved[moved.edge_open.abs() >= lo]
        if len(s) < 60:
            continue
        agree = ((s.edge_open > 0) & (s.move > 0)) | ((s.edge_open < 0) & (s.move < 0))
        w, l = int(agree.sum()), int(len(s) - agree.sum())
        print(f"  disagreement {lo}+: line moved our way {w} of {len(s)} "
              f"({100*w/len(s):.1f}%)   {verdict(w, l)}")
    print(f"  average move when we like the home side: "
          f"{moved[moved.edge_open > 0].move.mean():+.2f} points")
    print(f"  average move when we like the away side: "
          f"{moved[moved.edge_open < 0].move.mean():+.2f} points")

print("\n" + "=" * 78)
print("TEST 4 — PRICE CONSISTENCY. A book's moneyline against its own spread.")
print("=" * 78)
if BOOKS.empty:
    print("  no per-book moneylines came back")
else:
    B = BOOKS.merge(M[["season", "week", "home_team", "away_team", "margin", "fbs"]],
                    on=["season", "week", "home_team", "away_team"], how="inner")
    B = B[B.fbs & (B.spread.abs() <= PRICE_MAX)].copy()
    ph = np.where(B.hml > 0, 100 / (B.hml + 100), -B.hml / (-B.hml + 100))
    pa = np.where(B.aml > 0, 100 / (B.aml + 100), -B.aml / (-B.aml + 100))
    p = np.clip(ph / (ph + pa), 0.001, 0.999)
    B["equiv"] = -(GAME_SD * norm.ppf(p))
    B["diff"] = B.equiv - B.spread
    B["mkt"] = -B.spread
    B = B[B.margin != B.mkt]
    flagged = B[B["diff"].abs() >= PRICE_FLAG].copy()
    # the discrepancy says the spread is the better buy on one particular side
    side_home = flagged["diff"] < 0
    cov = flagged.margin > flagged.mkt
    winp = (side_home & cov) | (~side_home & ~cov)
    print(f"  eligible book quotes inside {PRICE_MAX} points: {len(B):,}")
    print(f"  {'threshold':<22} {'bets':>6} {'record':>13} {'win%':>8}   verdict")
    for thr in (PRICE_FLAG, 3.0, 4.0, 5.0):
        m2 = flagged["diff"].abs() >= thr
        report(m2, winp, f"{thr} points or more", flagged)

print("\n" + "=" * 78)
print("TEST 5 — SUBGROUPS, against the closing line")
print("=" * 78)
print(f"  {'group':<22} {'games':>6} {'record':>13} {'win%':>8}   verdict")
report(d.g5 & (d.edge.abs() >= 3), win1, "G5 vs G5, 3+ gap", d)
report(~d.g5 & (d.edge.abs() >= 3), win1, "not both G5, 3+ gap", d)
report(d.week <= 4, win1, "weeks 1-4", d)
report((d.week > 4) & (d.week <= 9), win1, "weeks 5-9", d)
report(d.week > 9, win1, "weeks 10+", d)

print("\n" + "=" * 78)
print("TEST 6 — TOTALS, against the closing total")
print("=" * 78)
t = F[F.total_close.notna() & (F.total != F.total_close)].copy()
if len(t) < 100:
    print("  not enough totals to test")
else:
    over = t.total > t.total_close
    w, l = int(over.sum()), int(len(t) - over.sum())
    print(f"  taking every over: {w}-{l} ({100*w/len(t):.1f}%) on {len(t):,} games   {verdict(w, l)}")
    # And the real question: does OUR total beat the market's? This needs the
    # points model refitted week by week, which is what fit_totals_as_of adds.
    # NOT called tm: the block below this one already uses that name for the
    # games with an opening total, which silently replaced this frame and made
    # the calibration measure 3,447 games it had never scored.
    tmod = t[t.model_total.notna()].copy()
    if len(tmod) >= 100:
        tmod["t_edge"] = tmod.model_total - tmod.total_close
        t_over = tmod.t_edge > 0
        t_hit = tmod.total > tmod.total_close
        win_t = (t_over & t_hit) | (~t_over & ~t_hit)
        print(f"  {'disagreement':<22} {'games':>6} {'record':>13} {'win%':>8}   verdict")
        for lo, hi, lab in ((0, 99, "any"), (0, 3, "0 to 3"), (3, 6, "3 to 6"),
                            (6, 99, "6 or more")):
            report((tmod.t_edge.abs() >= lo) & (tmod.t_edge.abs() < hi), win_t, lab, tmod)
        print(f"  our total missed by {float((tmod.total - tmod.model_total).abs().mean()):.2f} points "
              f"against the market's {float((tmod.total - tmod.total_close).abs().mean()):.2f}")
    if t.total_open.notna().sum() > 100:
        tm = t[t.total_open.notna()]
        print(f"  average total move from open to close: "
              f"{(tm.total_close - tm.total_open).mean():+.2f} points")

print("\n" + "=" * 78)
print("WHAT THE CARD IS ALLOWED TO DO")
print("=" * 78)
print(f"A strategy may become a graded pick only if its 95% interval sits ENTIRELY")
print(f"above {BREAK_EVEN}%. 'No evidence either way' is not permission. If nothing")
print("clears, the card keeps showing numbers and makes no picks, which is the")
print("honest outcome and not a failure of the build.")


# ------------------------------------------------------ write it back
# Everything above is printed for a person to read. This turns the same games
# into two things the card needs and could not previously get:
#
#   1. the record per strategy, which sets the tier
#   2. the CALIBRATION per strategy, which is the line that maps what the model
#      claims onto what actually happened
#
# Before this existed the records were copied out of this output by hand, and
# calibration was not measured at all, so the card graded on raw simulated
# probabilities that were known to be too confident.
print("\n" + "=" * 78)
print("CALIBRATION AND RECORD")
print("=" * 78)


def wl(mask, win):
    """Wins and losses under a mask, compared POSITIONALLY.

    These frames are filtered differently from each other, so a pandas boolean
    Series carries an index that may not line up with the one it is masking.
    Converting both to arrays first makes a length mismatch fail loudly here
    rather than align on labels and quietly measure the wrong games.
    """
    m = np.asarray(mask, dtype=bool); v = np.asarray(win, dtype=bool)
    if len(m) != len(v):
        raise ValueError(f"mask has {len(m)} rows, outcomes have {len(v)}")
    s = v[m]; w = int(s.sum()); return w, int(len(s) - w)


def keep(name, fn):
    """Run one measurement and carry on if it fails.

    A single bad frame used to lose the whole write, which left the card grading
    on the previous record while this output said otherwise. Each piece now
    stands or falls on its own, and says which."""
    try:
        return fn()
    except Exception as ex:
        print(f"  SKIPPED {name}: {ex}")
        return None


def margin_sd_at(total):
    a, b, base = [float(x) for x in MS.SIM["total_tilt"]]
    t = 52.0 if (total is None or not np.isfinite(total)) else float(total)
    return float(MS.SIM["margin_sd"]) * float(np.clip((a * t + b) / base, 0.85, 1.20))


def fit_probit(p_sim, won, min_n=150):
    """P(win) = Phi(a + k * Phi^-1(p_sim)), by maximum likelihood.

    k is deliberately NOT constrained to be positive. On both cards the measured
    slope has come out at or below zero, meaning a bigger disagreement did not
    win more often, and a constrained fit would hide exactly that.
    """
    p = np.clip(np.asarray(p_sim, dtype=float), 1e-6, 1 - 1e-6)
    y = np.asarray(won, dtype=float)
    ok = np.isfinite(p) & np.isfinite(y)
    p, y = p[ok], y[ok]
    if len(y) < min_n or y.max() == y.min():
        return None
    z = norm.ppf(p)

    def nll(th):
        q = np.clip(norm.cdf(th[0] + th[1] * z), 1e-9, 1 - 1e-9)
        return -np.sum(y * np.log(q) + (1 - y) * np.log(1 - q))

    r = minimize(nll, x0=np.array([0.0, 1.0]), method="BFGS")
    a, k = float(r.x[0]), float(r.x[1])
    try:
        se = np.sqrt(np.diag(r.hess_inv)); se_a, se_k = float(se[0]), float(se[1])
    except Exception:
        se_a = se_k = float("nan")
    return dict(a=round(a, 4), k=round(k, 4), se_a=round(se_a, 4), se_k=round(se_k, 4),
                n=int(len(y)), k_clears_zero=bool(k - 1.96 * se_k > 0))


def show(name, fit):
    if not fit:
        print(f"  {name:<18} not enough games to fit"); return
    if fit.get("level_only"):
        print(f"  {name:<18} a {fit['a']:+.4f}  no slope: this strategy has no model "
              f"input to calibrate, only a level   n {fit['n']:,}")
        return
    se = fit.get("se_k")
    se_txt = f"(se {se:.4f})" if isinstance(se, float) and np.isfinite(se) else "(se unavailable)"
    print(f"  {name:<18} a {fit['a']:+.4f}  k {fit['k']:+.4f} {se_txt}  "
          f"n {fit['n']:,}   {'k clears zero' if fit['k_clears_zero'] else 'k does not clear zero'}")


print("\n" + "=" * 78)
print("TEST 7 — MONEYLINE. Betting the straight winner, measured by return.")
print("=" * 78)
# A moneyline cannot be judged on win rate. A 35% underdog at +250 is profitable
# and a 90% favorite at -1200 is not, so this is measured as return per unit
# staked. It is also walk-forward twice over: the ratings are fitted from prior
# weeks only, and the calibration used to pick a side is fitted only on seasons
# BEFORE the one being bet, so no bet is chosen using its own outcome.
ml_rows = []
if BOOKS.empty:
    print("  no per-book moneylines came back")
else:
    def _imp(x):
        return np.where(x > 0, 100.0 / (x + 100.0), -x / (-x + 100.0))

    def _dec(x):
        return np.where(x > 0, 1.0 + x / 100.0, 1.0 + 100.0 / -x)

    # A moneyline is not a linear scale: it jumps from -100 to +100 with nothing
    # in between, so a median of the raw prices can land on a number that cannot
    # exist, and -inf returns follow. Convert each book's quote to a probability
    # and a decimal payout first, then take the median of those.
    BK = BOOKS.copy()
    for c in ("hml", "aml"):
        BK = BK[BK[c].abs().between(100, ML_SANE)]
    BK = BK[~((BK.hml < 0) & (BK.aml < 0))]
    ph_b, pa_b = _imp(BK.hml.values), _imp(BK.aml.values)
    BK = BK.assign(mkt_home=np.clip(ph_b / (ph_b + pa_b), 0.001, 0.999),
                   dec_home=_dec(BK.hml.values), dec_away=_dec(BK.aml.values))
    ML = (BK.groupby(["season", "week", "home_team", "away_team"])
          [["mkt_home", "dec_home", "dec_away"]].median().reset_index())
    Q = d.merge(ML, on=["season", "week", "home_team", "away_team"], how="inner")
    Q = Q[np.isfinite(Q.dec_home) & np.isfinite(Q.dec_away)
          & (Q.dec_home > 1.0) & (Q.dec_away > 1.0)]
    if len(Q) < 200:
        print(f"  only {len(Q)} games carry a usable two-sided moneyline, too few to test")
    else:
        sd_q = np.sqrt(float(MS.SIM["line_sd"]) ** 2
                       + np.array([margin_sd_at(x) for x in Q.total_close.values]) ** 2)
        Q = Q.assign(p_raw=norm.cdf(Q.model.values / sd_q),
                     home_won=(Q.margin.values > 0).astype(float))
        seasons = sorted(Q.season.unique())
        for s in seasons[1:]:
            past = Q[Q.season < s]
            fut = Q[Q.season == s]
            if len(past) < 400 or fut.empty:
                continue
            fit = fit_probit(past.p_raw.values, past.home_won.values, min_n=400)
            a_, k_ = (0.0, 1.0) if not fit else (fit["a"], fit["k"])
            p_cal = norm.cdf(a_ + k_ * norm.ppf(np.clip(fut.p_raw.values, 1e-6, 1 - 1e-6)))
            take_home = p_cal > fut.mkt_home.values
            dec = np.where(take_home, fut.dec_home.values, fut.dec_away.values)
            won = np.where(take_home, fut.home_won.values > 0, fut.home_won.values == 0)
            ml_rows.append(pd.DataFrame(dict(
                season=s, won=won.astype(float),
                ret=np.where(won, dec - 1.0, -1.0),
                edge=np.abs(p_cal - fut.mkt_home.values) * 100,
                p_cal=np.where(take_home, p_cal, 1 - p_cal),
                dog=(dec > 2.0))))
        if ml_rows:
            R7 = pd.concat(ml_rows, ignore_index=True)
            def _line(label, sub):
                if len(sub) < 100:
                    return
                w = int(sub.won.sum()); l = len(sub) - w
                roi = float(sub.ret.mean()) * 100
                se = float(sub.ret.std(ddof=1)) / np.sqrt(len(sub)) * 100
                lo, hi = roi - 1.96 * se, roi + 1.96 * se
                verdict = ("CLEARS, the whole interval is above zero" if lo > 0 else
                           "loses, the whole interval is below zero" if hi < 0 else
                           "no evidence either way")
                print(f"  {label:<22} {len(sub):>6} {f'{w}-{l}':>13} {roi:>+7.1f}%   "
                      f"({lo:+.1f} to {hi:+.1f})  {verdict}")
            print(f"  {'group':<22} {'bets':>6} {'record':>13} {'return':>8}   95% interval")
            _line("every game", R7)
            _line("we take the dog", R7[R7.dog])
            _line("we take the favorite", R7[~R7.dog])
            for lo_ in (2, 5, 10):
                _line(f"edge {lo_}+ points", R7[R7.edge >= lo_])
        else:
            print("  not enough seasons to run this walk-forward")



# ============================================================================
# ROSTER TURNOVER. Section 4.4 calls this the leading known defect. 4.5a asked
# for returning production as a Week-1 shrinkage term.
#
# The first version of this test answered "no measurable improvement" and that
# answer was WRONG, for a reason worth writing down. It compared two versions on
# the SAME games and then judged the difference against the spread of the errors
# themselves. That is the wrong ruler. Both versions face the same hard games,
# so most of that spread cancels; the honest test is game by game, on the paired
# difference in absolute error. Measured on this data the paired ruler is about
# seven times tighter, which is the difference between finding a real effect and
# calling it noise.
#
# Three other things that first version got wrong, all fixed here:
#   - it stopped the grid at 0.5, and 0.5 won, so it never found where the
#     effect turns over
#   - it tested week 1 only, which is about 40 games a season, the smallest
#     sample available, when the same defect plainly persists into weeks 2-4
#   - it fixed the fade at four games because that is what 4.5a suggested,
#     rather than letting the data choose how long the correction should last
# ============================================================================
print("\n" + "=" * 78)
print("TEST 8 - ROSTER TURNOVER, PAIRED")
print("=" * 78)

TURN_STRENGTH = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
TURN_FADE = (1.0, 4.0, 8.0, 14.0)  # 1 is week 1 only, 14 never fades in-season
# fade 1 was added after the first paired run showed the effect is real in week 1
# (+0.16 points, interval just clear of zero) and NEGATIVE by week 4. Fading over
# four games leaves partial shrinkage on teams that now have their own games, and
# that is where the damage comes from. Fade 1 switches it off the moment a team
# has played once, which is what 4.5a asked for in the first place.
TURN_WEEKS = (1, 2, 3, 4)

turnover = {}
try:
    if not returning:
        print("  no returning production came back, so this cannot be tested")
    else:
        WK = LINES.merge(G, on=["season", "week", "home_team", "away_team"], how="inner")
        both_fbs = np.array([is_fbs(h) and is_fbs(a)
                             for h, a in zip(WK.home_team, WK.away_team)])
        WK = WK[WK.week.isin(TURN_WEEKS).values & both_fbs]
        WK = WK[np.isfinite(WK.close.values)].reset_index(drop=True)
        if len(WK) < 300:
            print(f"  only {len(WK)} games in weeks 1-4 carry a line, too few")
        else:
            per_week = WK.week.value_counts().sort_index().to_dict()
            print(f"  {len(WK)} FBS vs FBS games in weeks 1-4 with a closing line, "
                  f"{WK.season.nunique()} seasons")
            print(f"  by week: " + ", ".join(f"wk{k} {v}" for k, v in per_week.items()))

            _cache = {}

            def fitted(season, week, strength, fade):
                # week 1 has no games of its own, so fade cannot matter there;
                # collapse it so the cache is not doing the same work three times
                f = 0.0 if week == 1 else fade
                k = (season, week, round(float(strength), 3), round(float(f), 3))
                if k not in _cache:
                    try:
                        _cache[k] = fit_as_of(season, week, ret_strength=strength,
                                              ret_fade=fade)
                    except Exception:
                        _cache[k] = (None, None)
                return _cache[k]

            def predict(strength, fade):
                """Predicted home margin for every game, aligned to WK's index."""
                out = np.full(len(WK), np.nan)
                for (s_, w_), grp in WK.groupby(["season", "week"]):
                    R_, hfa_ = fitted(int(s_), int(w_), strength, fade)
                    if R_ is None:
                        continue
                    out[grp.index.values] = (
                        R_.reindex(grp.home_team).values
                        - R_.reindex(grp.away_team).values
                        + np.where(grp.neutral.values, 0.0, hfa_))
                return out

            act = WK.margin.values
            mkt = -WK.close.values
            base = predict(0.0, 4.0)
            ok = np.isfinite(base) & np.isfinite(act)
            base_err = np.abs(act - base)
            print(f"\n  doing nothing: our MAE {base_err[ok].mean():.2f}, "
                  f"market MAE {np.abs(act - mkt)[ok].mean():.2f}, "
                  f"on {int(ok.sum())} games")
            print(f"\n  {'shrink':>7} {'fade':>5} {'gain':>8} {'95% interval':>18} "
                  f"{'better':>7} {'worse':>6}   verdict")
            grid = []
            for fade in TURN_FADE:
                for strength in TURN_STRENGTH:
                    if strength == 0.0 and fade != TURN_FADE[0]:
                        continue                      # identical to doing nothing
                    p = predict(strength, fade)
                    m_ = ok & np.isfinite(p)
                    if m_.sum() < 200:
                        continue
                    # PAIRED: per game, did the adjustment move us closer?
                    # NOT d: that is the module-level merged frame, used after
                    # this block. Shadowing it broke the state write once already.
                    dd = base_err[m_] - np.abs(act[m_] - p[m_])
                    gain = float(dd.mean())
                    se = float(dd.std(ddof=1) / np.sqrt(m_.sum()))
                    lo, hi = gain - 1.96 * se, gain + 1.96 * se
                    call = ("HELPS" if lo > 0 else
                            "hurts" if hi < 0 else "no evidence")
                    row = dict(strength=strength, fade=fade, n=int(m_.sum()),
                               gain=round(gain, 4), se=round(se, 4),
                               lo=round(lo, 4), hi=round(hi, 4), verdict=call,
                               better=int((dd > 0).sum()), worse=int((dd < 0).sum()))
                    grid.append(row)
                    if strength > 0:
                        print(f"  {strength:>7.1f} {fade:>5.0f} {gain:>+8.3f} "
                              f"{f'({lo:+.3f} to {hi:+.3f})':>18} "
                              f"{row['better']:>7} {row['worse']:>6}   {call}")
            live = [r for r in grid if r["strength"] > 0]
            best = max(live, key=lambda r: r["gain"]) if live else None
            if best:
                print(f"\n    best: shrink {best['strength']:.1f}, fade {best['fade']:.0f} "
                      f"-> {best['gain']:+.3f} points per game "
                      f"({best['lo']:+.3f} to {best['hi']:+.3f}), {best['verdict']}")
                if best["strength"] == max(TURN_STRENGTH):
                    print("    NOTE: the best setting is the strongest one tried, so the "
                          "grid may still be too narrow.")
                # where does it help? by week, at the best setting
                p = predict(best["strength"], best["fade"])
                byweek = []
                for w_ in TURN_WEEKS:
                    m_ = ok & np.isfinite(p) & (WK.week.values == w_)
                    if m_.sum() < 50:
                        continue
                    dd = base_err[m_] - np.abs(act[m_] - p[m_])
                    se = float(dd.std(ddof=1) / np.sqrt(m_.sum()))
                    byweek.append(dict(week=int(w_), n=int(m_.sum()),
                                       gain=round(float(dd.mean()), 4),
                                       lo=round(float(dd.mean()) - 1.96 * se, 4),
                                       hi=round(float(dd.mean()) + 1.96 * se, 4)))
                print(f"\n  where it helps, at the best setting:")
                print(f"  {'week':>5} {'games':>6} {'gain':>8} {'95% interval':>18}")
                for b in byweek:
                    print(f"  {b['week']:>5} {b['n']:>6} {b['gain']:>+8.3f} "
                          f"{f'({b[chr(108)+chr(111)]:+.3f} to {b[chr(104)+chr(105)]:+.3f})':>18}")
                turnover = dict(grid=grid, best=best, by_week=byweek,
                                games=int(ok.sum()),
                                base_mae=round(float(base_err[ok].mean()), 3),
                                market_mae=round(float(np.abs(act - mkt)[ok].mean()), 3),
                                method="paired difference in absolute error, "
                                       "same games, walk-forward")
except Exception as ex:
    import traceback
    print(f"  SKIPPED turnover test: {ex}")
    traceback.print_exc(file=sys.stdout)


# ============================================================================
# TEST 9 - PER-PLAY EFFICIENCY, PAIRED
#
# Section 5.1: the NFL card rates teams on play-by-play efficiency, the college
# card on game margins, because college play-by-play is not freely available.
# PPA is the part that is: one number per team per game for what each play was
# worth, with garbage time excluded.
#
# The question is not "is efficiency a better description of a game" - it plainly
# is, that is why the NFL card uses it. The question is whether fitting the
# ratings on it makes NEXT week's prediction closer to the actual margin than
# fitting on the scoreboard does. Those are different claims and only the second
# one is worth anything here.
#
# Same ruler as Test 8, and for the same reason: paired, game by game, on the
# difference in absolute error. Judging this against the spread of the errors
# themselves would be about seven times too loose and would call a real effect
# noise, which is exactly the mistake Test 8 was rewritten to fix.
#
# The weight is a switch that defaults to 0, and at 0 the fit is the model the
# card publishes, unchanged. Nothing here is wired into build_ratings.py or
# model_state.json: until it earns its way on there is nothing for the live model
# to read, and a constant sitting in two places is 4.3h waiting to happen.
# ============================================================================
print("\n" + "=" * 78)
print("TEST 9 - PER-PLAY EFFICIENCY, PAIRED")
print("=" * 78)

PPA_WEIGHT = (0.25, 0.5, 0.75, 1.0)   # 0 is the current model and is the baseline

efficiency = {}
try:
    if not ppa or not np.isfinite(G.eff.values).any():
        print("  no per-play efficiency came back, so this cannot be tested")
    else:
        EW = LINES.merge(G, on=["season", "week", "home_team", "away_team"], how="inner")
        _fbs_only = np.array([is_fbs(h) and is_fbs(a)
                              for h, a in zip(EW.home_team, EW.away_team)])
        EW = EW[_fbs_only]
        EW = EW[np.isfinite(EW.close.values)].reset_index(drop=True)
        if len(EW) < 500:
            print(f"  only {len(EW)} graded games, too few")
        else:
            cov = float(np.isfinite(EW.eff.values).mean())
            print(f"  {len(EW):,} FBS vs FBS games with a closing line across "
                  f"{EW.season.nunique()} seasons")
            print(f"  {100 * cov:.0f}% of them carry an efficiency figure of their own; "
                  f"a game without one is fitted on its margin as before")

            _ecache = {}

            def eff_fitted(season, week, weight):
                key = (int(season), int(week), round(float(weight), 3))
                if key not in _ecache:
                    try:
                        _ecache[key] = fit_as_of(season, week, ppa_weight=weight)
                    except Exception:
                        _ecache[key] = (None, None)
                return _ecache[key]

            def eff_predict(weight):
                out = np.full(len(EW), np.nan)
                for (s_, w_), grp in EW.groupby(["season", "week"]):
                    R_, hfa_ = eff_fitted(int(s_), int(w_), weight)
                    if R_ is None:
                        continue
                    out[grp.index.values] = (
                        R_.reindex(grp.home_team).values
                        - R_.reindex(grp.away_team).values
                        + np.where(grp.neutral.values, 0.0, hfa_))
                return out

            e_act = EW.margin.values
            e_mkt = -EW.close.values
            e_base = eff_predict(0.0)
            e_ok = np.isfinite(e_base) & np.isfinite(e_act)
            e_baseerr = np.abs(e_act - e_base)
            print(f"\n  fitting on the scoreboard: our MAE "
                  f"{e_baseerr[e_ok].mean():.3f}, market MAE "
                  f"{np.abs(e_act - e_mkt)[e_ok].mean():.3f}, on {int(e_ok.sum()):,} games")

            print(f"\n  {'weight':>7} {'gain':>8} {'95% interval':>18} "
                  f"{'better':>7} {'worse':>6}   verdict")
            e_grid = []
            for weight in PPA_WEIGHT:
                p_ = eff_predict(weight)
                m_ = e_ok & np.isfinite(p_)
                if m_.sum() < 400:
                    continue
                dd = e_baseerr[m_] - np.abs(e_act[m_] - p_[m_])
                gain = float(dd.mean())
                se = float(dd.std(ddof=1) / np.sqrt(m_.sum()))
                lo, hi = gain - 1.96 * se, gain + 1.96 * se
                call = "HELPS" if lo > 0 else "hurts" if hi < 0 else "no evidence"
                e_grid.append(dict(weight=weight, n=int(m_.sum()),
                                   gain=round(gain, 4), se=round(se, 4),
                                   lo=round(lo, 4), hi=round(hi, 4), verdict=call,
                                   better=int((dd > 0).sum()),
                                   worse=int((dd < 0).sum())))
                print(f"  {weight:>7.2f} {gain:>+8.3f} "
                      f"{f'({lo:+.3f} to {hi:+.3f})':>18} "
                      f"{int((dd > 0).sum()):>7} {int((dd < 0).sum()):>6}   {call}")

            e_best = max(e_grid, key=lambda r: r["gain"]) if e_grid else None
            e_bywk = []
            if e_best:
                print(f"\n    best: weight {e_best['weight']:.2f} -> "
                      f"{e_best['gain']:+.3f} points per game "
                      f"({e_best['lo']:+.3f} to {e_best['hi']:+.3f}), {e_best['verdict']}")
                if e_best["weight"] == max(PPA_WEIGHT):
                    print("    NOTE: the best setting is the strongest tried, so the grid "
                          "may still be too narrow.")
                p_ = eff_predict(e_best["weight"])
                for lbl, sel in (("weeks 1-4", EW.week.values <= 4),
                                 ("weeks 5 on", EW.week.values > 4)):
                    m_ = e_ok & np.isfinite(p_) & sel
                    if m_.sum() < 100:
                        continue
                    dd = e_baseerr[m_] - np.abs(e_act[m_] - p_[m_])
                    se = float(dd.std(ddof=1) / np.sqrt(m_.sum()))
                    e_bywk.append(dict(span=lbl, n=int(m_.sum()),
                                       gain=round(float(dd.mean()), 4),
                                       lo=round(float(dd.mean()) - 1.96 * se, 4),
                                       hi=round(float(dd.mean()) + 1.96 * se, 4)))
                print(f"\n  where it helps, at the best setting:")
                print(f"  {'span':>11} {'games':>6} {'gain':>8} {'95% interval':>18}")
                for b in e_bywk:
                    iv = "({:+.3f} to {:+.3f})".format(b["lo"], b["hi"])
                    print(f"  {b['span']:>11} {b['n']:>6} {b['gain']:>+8.3f} {iv:>18}")
                efficiency = dict(grid=e_grid, best=e_best, by_span=e_bywk,
                                  games=int(e_ok.sum()),
                                  coverage=round(cov, 3),
                                  base_mae=round(float(e_baseerr[e_ok].mean()), 3),
                                  market_mae=round(float(np.abs(e_act - e_mkt)[e_ok].mean()), 3),
                                  method="paired difference in absolute error, same "
                                         "games, walk-forward; points per unit of "
                                         "efficiency refitted at every point in time")
except Exception as ex:
    import traceback
    print(f"  SKIPPED efficiency test: {ex}")
    traceback.print_exc(file=sys.stdout)


record, notes, calibration, subgroups = {}, {}, {}, {}
try:
    LINE_SD = float(MS.SIM["line_sd"])
    e = d.edge.abs()

    # The simulated probability the card would have shown, in closed form. The
    # card draws the true line around our number and then the game around that,
    # so the margin is normal about our number with the two variances added.
    sd_g = np.sqrt(LINE_SD ** 2 + np.array([margin_sd_at(t) for t in d.total_close.values]) ** 2)
    p_spread = norm.cdf(e.values / sd_g)

    record["model_gap_early"] = keep("model_gap_early", lambda: wl(d.week <= 4, win1))
    record["model_gap_late"] = keep("model_gap_late", lambda: wl(d.week > 4, win1))
    notes["model_gap_early"] = "our number vs the close, weeks 1-4"
    notes["model_gap_late"] = "our number vs the close, weeks 5 on"
    early = (d.week <= 4).values
    calibration["model_gap_early"] = keep("cal early", lambda: fit_probit(p_spread[early], win1.values[early]))
    calibration["model_gap_late"] = keep("cal late", lambda: fit_probit(p_spread[~early], win1.values[~early]))

    # Outright winner. This is the confidence question rather than the value one,
    # and it is a different prediction: a model can know who wins without being
    # able to beat the number.
    sd_o = np.sqrt(LINE_SD ** 2 + np.array([margin_sd_at(t) for t in d.total_close.values]) ** 2)
    p_home = norm.cdf(d.model.values / sd_o)
    home_won = (d.margin.values > 0).astype(float)
    ok = d.margin.values != 0
    calibration["outright"] = keep("outright", lambda: fit_probit(p_home[ok], home_won[ok]))
    # Deliberately NOT written into record. Home teams win most college games, so
    # a "record" here would read as a strategy clearing break-even when it is
    # nothing of the kind. Outright is a confidence calibration, not a bet.

    if "flagged" in globals() and len(flagged):
        thr = float(MS.TH["price_pick"])
        record["price_gap"] = keep("price_gap", lambda: wl(flagged["diff"].abs() >= thr, winp))
        notes["price_gap"] = f"a book's moneyline against its own spread, {thr:g}+ points"
        # This replaces the assumed "3 points per 10%" mapping with a fitted one.
        pg_edge = flagged["diff"].abs().values
        pg_p = np.minimum(0.5 + pg_edge / 30.0, 0.75)
        calibration["price_gap"] = keep("cal price_gap", lambda: fit_probit(pg_p, winp.values.astype(float)))

    if "over" in globals() and len(t):
        record["total_over"] = (int(over.sum()), int(len(t) - over.sum()))
        notes["total_over"] = "the market total, taken over every game, no model input"
        # A baseline with no model in it, so there is a level and no slope.
        calibration["total_over"] = dict(a=round(float(norm.ppf(over.mean())), 4), k=0.0,
                                         se_a=None, se_k=None, n=int(len(t)),
                                         k_clears_zero=False, level_only=True)

    if "win_t" in globals() and "tmod" in globals() and len(tmod) >= 100:
        record["total_model"] = keep("total_model", lambda: wl(np.ones(len(win_t), dtype=bool), win_t))
        notes["total_model"] = "our total against the close, the model version"
        sd_t = float(np.sqrt(float(MS.SIM["total_line_sd"]) ** 2 + float(MS.SIM["total_sd"]) ** 2))
        p_tot = norm.cdf(tmod.t_edge.abs().values / sd_t)
        calibration["total_model"] = keep("cal total_model", lambda: fit_probit(p_tot, win_t.values.astype(float)))

    for k_, f_ in calibration.items():
        show(k_, f_)

    # The subgroups this test already computes and used to throw away. Section
    # 6.8 says a quieter market is where an edge would live, so these are the
    # places worth looking, and they are now kept rather than printed once.
    def sub(name, mask, win, label):
        w, l = wl(mask, win)
        if w + l >= 100:
            subgroups[name] = dict(w=w, l=l, pct=round(100 * w / (w + l), 1),
                                   interval=[round(x, 1) for x in wilson(w, w + l)],
                                   label=label)

    keep("subgroups", lambda: sub("g5_vs_g5", d.g5 & (e >= 3), win1, "both sides Group of 5, 3+ point gap"))
    sub("not_g5", ~d.g5 & (e >= 3), win1, "at least one side P4, 3+ point gap")
    sub("weeks_1_4", d.week <= 4, win1, "weeks 1 to 4")
    sub("weeks_5_9", (d.week > 4) & (d.week <= 9), win1, "weeks 5 to 9")
    sub("weeks_10_plus", d.week > 9, win1, "weeks 10 and later")
    for lo, hi in ((0, 3), (3, 6), (6, 10), (10, 99)):
        sub(f"gap_{lo}_{hi}", (e >= lo) & (e < hi), win1, f"gap {lo} to {hi} points")

    # Does the older half of the window behave like the newer half? If it does
    # not, the extra seasons are describing a different sport and should not be
    # pooled. This is reported rather than acted on automatically.
    mid = TEST[len(TEST) // 2]
    for lab, m in (("older_half", d.season < mid), ("newer_half", d.season >= mid)):
        w, l = wl(m, win1)
        if w + l >= 100:
            subgroups[lab] = dict(w=w, l=l, pct=round(100 * w / (w + l), 1),
                                  interval=[round(x, 1) for x in wilson(w, w + l)],
                                  label=f"{'before' if lab=='older_half' else 'from'} {mid}")

    print("\n  subgroups kept:")
    for name, s in subgroups.items():
        print(f"    {name:<16} {s['w']}-{s['l']}  {s['pct']:.1f}%  "
              f"({s['interval'][0]:.1f} to {s['interval'][1]:.1f})   {s['label']}")

    headline = {
        "model_gap_pct": round(100 * win1.sum() / max(len(d), 1), 1),
        "model_gap_games": int(len(d)),
        "market_mae": round(float((d.margin - d.mkt_close).abs().mean()), 2),
        "model_mae": round(float((d.margin - d.model).abs().mean()), 2),
    }

    # The card's How to read tab quotes these two buckets. Written fresh here so
    # they cannot survive from an earlier run once this one has superseded them.
    legacy = {}
    for lo, hi, key in ((3, 6, "edge_3_6"), (6, 10, "edge_6_10")):
        w, l = wl((e >= lo) & (e < hi), win1)
        if w + l:
            legacy[f"{key}_pct"] = round(100 * w / (w + l), 1)
            legacy[f"{key}_games"] = w + l

    # The moneyline is stored with its RETURN, not just a win-loss line. A tier
    # read off a win rate would be meaningless here: the prices differ on every
    # bet, so 40% of underdogs can pay and 85% of favorites can lose money.
    returns = {}
    if "R7" in globals() and len(R7) >= 100:
        # Split by side. Taking the favorite and taking the underdog are not the
        # same bet and they did not do the same thing, so they are stored as two
        # strategies and the card grades them separately.
        for key, sub, label in (("moneyline", R7, "our calibrated winner against the price"),
                                ("moneyline_fav", R7[~R7.dog], "same, where we land on the favorite"),
                                ("moneyline_dog", R7[R7.dog], "same, where we land on the underdog")):
            if len(sub) < 100:
                continue
            roi = float(sub.ret.mean()) * 100
            se = float(sub.ret.std(ddof=1)) / np.sqrt(len(sub)) * 100
            w = int(sub.won.sum())
            record[key] = (w, int(len(sub) - w))
            notes[key] = label + ", walk-forward"
            returns[key] = dict(n=int(len(sub)), roi=round(roi, 2), se=round(se, 2),
                                lo=round(roi - 1.96 * se, 2), hi=round(roi + 1.96 * se, 2),
                                w=w, l=int(len(sub) - w))
            print(f"  {key:<18} {w}-{int(len(sub)-w)}  return {roi:+.1f}% "
                  f"({roi-1.96*se:+.1f} to {roi+1.96*se:+.1f})")


    # ------------------------------------------------- the confidence floor
    # cfb_picks.py caps a grade at D when the calibrated probability of the
    # pick winning sits under CONF_FLOOR. That number was CHOSEN at 40, and a
    # chosen number inside a scheme whose whole point is measured evidence is
    # the same defect as any other. This measures it instead.
    #
    # It is measured on the moneyline and nowhere else, deliberately. A spread
    # pick always takes the side we favour, so its probability starts at 50%
    # and a floor below that can never bite. The moneyline is the only market
    # where we land on a real underdog and the price alone would otherwise
    # carry the grade, which is exactly the case the floor exists to stop.
    #
    # The question is not "did these win". A 38% shot at +220 is supposed to
    # lose most of the time. The question is whether they made money.
    conf_floor = {}
    if "R7" in globals() and len(R7) >= 100:
        cf_buckets = []
        cf_edges = [0, 35, 40, 45, 50, 100]
        pc = R7.p_cal.values * 100
        for lo_, hi_ in zip(cf_edges[:-1], cf_edges[1:]):
            s_ = R7[(pc >= lo_) & (pc < hi_)]
            if len(s_) < 60:
                continue
            roi_ = float(s_.ret.mean()) * 100
            se_ = float(s_.ret.std(ddof=1)) / np.sqrt(len(s_)) * 100
            w_ = int(s_.won.sum())
            cf_buckets.append(dict(lo=lo_, hi=hi_, n=int(len(s_)), w=w_,
                                   l=int(len(s_) - w_), roi=round(roi_, 2),
                                   interval=[round(roi_ - 1.96 * se_, 2),
                                             round(roi_ + 1.96 * se_, 2)]))
        # Count up from the bottom. The floor is the top of the longest opening
        # run of buckets whose WHOLE interval sits below zero. The moment a
        # bucket is merely bad, or undecided, the run stops: "probably loses"
        # is not evidence enough to cap a grade at D.
        measured = None
        for b in cf_buckets:
            if b["interval"][1] < 0:
                measured = b["hi"]
            else:
                break
        losers = ["%d-%d%%" % (b["lo"], b["hi"]) for b in cf_buckets
                  if b["interval"][1] < 0]
        if measured is None:
            note = ("no bucket at the BOTTOM lost with its whole interval below zero, "
                    "so there is no measured floor and the chosen one stands")
            if losers:
                # Worth saying out loud, because it is the opposite of what the
                # floor was built for. A floor is a cut from below. If the only
                # buckets that clearly lose are high-probability ones, the
                # problem is not that unlikely calls are being oversold, it is
                # that likely ones are priced against us -- and that is already
                # handled, because those bets belong to a strategy whose own
                # backtested return caps them.
                note += (". The buckets that did lose outright were "
                         + ", ".join(losers) + ", which a floor cannot reach")
        else:
            note = (f"every bucket below {measured}% lost with its whole 95% interval "
                    f"below zero")
        conf_floor = dict(buckets=cf_buckets, measured=measured,
                          basis="moneyline bets, bucketed by calibrated probability, judged on return",
                          note=note)
        print("\n  confidence floor. Moneyline bets by calibrated probability, on return:")
        print(f"    {'bucket':<14} {'bets':>6} {'record':>12} {'return':>8}   95% interval")
        for b in cf_buckets:
            band_ = "%d-%d%%" % (b["lo"], b["hi"])
            rec = "%d-%d" % (b["w"], b["l"])
            iv = "(%+.1f to %+.1f)" % (b["interval"][0], b["interval"][1])
            print(f"    {band_:<14} {b['n']:>6} {rec:>12} {b['roi']:>+7.1f}%   {iv}")
        print(f"    -> {note}")

    # -------------------------------------------------- window sensitivity
    # SEASONS starts at 2016 because 2017 is the start of the transfer portal
    # era and line coverage thins out before it. That is a judgement, and a
    # judgement that moves the answer is a finding rather than a footnote.
    # This re-reports the headline on windows that drop the earliest seasons
    # one at a time. Same verdict on every window and the start year is doing
    # no work. A verdict that flips means the window is doing the work, and
    # the result is not safe to quote.
    sensitivity = {}
    for start in TEST:
        m_ = (d.season >= start).values
        w_, l_ = wl(m_, win1)
        if w_ + l_ < 200:
            continue
        lo_, hi_ = wilson(w_, w_ + l_)
        sensitivity[str(start)] = dict(
            w=w_, l=l_, n=w_ + l_, pct=round(100 * w_ / (w_ + l_), 1),
            interval=[round(lo_, 1), round(hi_, 1)],
            verdict=("clears" if lo_ > BREAK_EVEN else
                     "loses" if hi_ < BREAK_EVEN else "no evidence"))
    sens_summary = {}
    if sensitivity:
        verdicts = sorted({v["verdict"] for v in sensitivity.values()})
        # A verdict that changes as the window shrinks is not by itself evidence
        # that anything changed. Fewer games means a wider interval, and a wider
        # interval stops excluding break-even on its own. The question that
        # separates the two: does the win RATE move, or only the interval? Any
        # window whose win rate still sits inside the full window's interval is
        # saying the same thing more quietly. One that sits outside is saying
        # something different.
        full = sensitivity[str(TEST[0])]
        flo, fhi = full["interval"]
        drifted = sorted(s_ for s_, v in sensitivity.items()
                         if not (flo <= v["pct"] <= fhi))
        sens_summary = dict(stable=len(verdicts) == 1, verdicts=verdicts,
                            drifted=drifted, full_interval=[flo, fhi],
                            full_pct=full["pct"])
        print("\n  window sensitivity. Our number against the close, "
              "dropping the earliest seasons:")
        print(f"    {'from':<8} {'games':>7} {'record':>13} {'win rate':>9}   95% interval")
        for s_, v in sensitivity.items():
            rec = "%d-%d" % (v["w"], v["l"])
            iv = "(%.1f to %.1f)" % (v["interval"][0], v["interval"][1])
            print(f"    {s_:<8} {v['n']:>7,} {rec:>13} {v['pct']:>8.1f}%   {iv}  {v['verdict']}")
        if len(verdicts) == 1:
            print(f"    -> same verdict on every window ({verdicts[0]}), "
                  f"so the start year is not doing the work")
        elif not drifted:
            print(f"    -> the label changes ({', '.join(verdicts)}) but every window's win "
                  f"rate still sits inside the full window's {flo:.1f} to {fhi:.1f}. That is a "
                  f"shrinking sample widening its interval, not the sport changing.")
        else:
            print(f"    -> the label changes ({', '.join(verdicts)}) AND the win rate moves: "
                  f"{', '.join(drifted)} sit outside the full window's {flo:.1f} to {fhi:.1f}. "
                  f"The start year is doing some of the work, so the pooled figure is not "
                  f"safe to quote on its own. Note the recent windows are also the smallest.")

    payload = {
        "run_utc": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window": f"{TEST[0]}-{TEST[-1]}, walk-forward, FBS vs FBS, real closing lines",
        "record": {k_: list(v) for k_, v in record.items() if v},
        "record_notes": notes,
        "headline": headline,
        "calibration": {**legacy, **{k_: v for k_, v in calibration.items() if v}},
        "subgroups": subgroups,
        "returns": returns,
        "conf_floor": conf_floor,
        "sensitivity": sensitivity,
        "sensitivity_summary": sens_summary,
        "turnover": turnover,
        "efficiency": efficiency,
    }
    for k_, (w, l) in record.items():
        n_ = w + l
        print(f"  {k_:<18} {w}-{l}  ({100 * w / max(n_, 1):.1f}% of {n_:,})")
    print(f"  our error {headline['model_mae']} points against the market's "
          f"{headline['market_mae']}")
    MS.save("backtest", payload)
    print("  cfb_picks.py and cfb_card.py will pick this up on the next run. "
          "Nothing to paste.")
except Exception as ex:
    import traceback
    print(f"  WARNING: could not write model_state.json ({ex})")
    traceback.print_exc(file=sys.stdout)
    print("  The findings above are correct but the card is still using the "
          "record from the previous run.")
