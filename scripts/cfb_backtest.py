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
from scipy.stats import norm
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
if MS.FELL_BACK:
    sys.exit(f"ERROR: {MS.FELL_BACK}. This will not run on guessed constants, because "
             f"its whole job is to say what the live model does. Fix "
             f"scripts/model_state.json and run it again.")
# ---- backtest-only ----
SEASONS = [2021, 2022, 2023, 2024, 2025]
TEST = [2022, 2023, 2024, 2025]

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
    "homeClassification": "home_div", "awayClassification": "away_div",
    "homeConference": "home_conf", "awayConference": "away_conf"})
G["neutral"] = G["neutral"].fillna(False).astype(bool)
G = G.dropna(subset=["home_points", "away_points"]).copy()
G["margin"] = G.home_points - G.away_points
G["total"] = G.home_points + G.away_points
print(f"\ncompleted games loaded: {len(G):,}")

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


def fit_as_of(season, week):
    hist = GB[(GB.season == season - 1) | ((GB.season == season) & (GB.week < week))]
    if len(hist) < 200:
        return None, None
    maxw = week - 1
    cur = (hist.season == season).values
    age = np.where(cur, maxw - hist.week.values, maxw + (15 - hist.week.values))
    w = 0.5 ** (age.astype(float) / HALF_LIFE)
    w = np.where(cur, w, w * CARRY)
    prior = talent_prior(season)
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
    return R, hfa


out = []
for season in TEST:
    for week in sorted(GB[GB.season == season].week.unique()):
        R, hfa = fit_as_of(season, week)
        if R is None:
            continue
        cur = GB[(GB.season == season) & (GB.week == week)]
        for _, gg in cur.iterrows():
            if gg.home_team == "OTHER" or gg.away_team == "OTHER":
                continue
            out.append(dict(season=season, week=week, home_team=gg.home_team,
                            away_team=gg.away_team,
                            model=float(R[gg.home_team] - R[gg.away_team]
                                        + (0.0 if gg.neutral else hfa)),
                            margin=gg.margin, total=gg.total,
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
    print(f"  overs went {w}-{l} ({100*w/len(t):.1f}%) on {len(t):,} games   {verdict(w, l)}")
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
# Everything above is printed for a person to read. This writes the same
# findings into model_state.json, which is where cfb_picks.py reads the records
# that set every grade and cfb_card.py reads the figures it quotes. Before this
# existed the records were copied out of this output by hand, which is the one
# step between a re-run and the card telling the truth.
print("\n" + "=" * 78)
print("WRITING THE RECORD")
print("=" * 78)


def wl(mask, win):
    """Wins and losses under a mask, as plain ints."""
    s = win[mask]
    w = int(s.sum())
    return w, int(len(s) - w)


record, notes = {}, {}
try:
    e = d.edge.abs()
    record["model_gap_early"] = wl(d.week <= 4, win1)
    record["model_gap_late"] = wl(d.week > 4, win1)
    notes["model_gap_early"] = "our number vs the close, weeks 1-4"
    notes["model_gap_late"] = "our number vs the close, weeks 5 on"

    if "flagged" in globals() and len(flagged):
        thr = float(MS.TH["price_pick"])
        record["price_gap"] = wl(flagged["diff"].abs() >= thr, winp)
        notes["price_gap"] = (f"a book's moneyline against its own spread, "
                              f"{thr:g}+ points")

    if "over" in globals() and len(t):
        record["total_over"] = (int(over.sum()), int(len(t) - over.sum()))
        notes["total_over"] = "the market total"

    headline = {
        "model_gap_pct": round(100 * win1.sum() / max(len(d), 1), 1),
        "model_gap_games": int(len(d)),
        "market_mae": round(float((d.margin - d.mkt_close).abs().mean()), 2),
        "model_mae": round(float((d.margin - d.model).abs().mean()), 2),
    }

    # The calibration figures the card quotes on its How to read tab: what the
    # model's own confidence buckets actually did.
    cal = {}
    for lo, hi, key in ((3, 6, "edge_3_6"), (6, 10, "edge_6_10")):
        m2 = (e >= lo) & (e < hi)
        w, l = wl(m2, win1)
        if w + l:
            cal[f"{key}_pct"] = round(100 * w / (w + l), 1)
            cal[f"{key}_games"] = w + l

    payload = {
        "run_utc": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window": f"{TEST[0]}-{TEST[-1]}, walk-forward, FBS vs FBS, real closing lines",
        "record": {k: list(v) for k, v in record.items()},
        "record_notes": notes,
        "headline": headline,
        "calibration": cal,
    }
    for k, (w, l) in record.items():
        n = w + l
        print(f"  {k:<18} {w}-{l}  ({100 * w / max(n, 1):.1f}% of {n:,})")
    print(f"  our error {headline['model_mae']} points against the market's "
          f"{headline['market_mae']}")
    MS.save("backtest", payload)
    print("  cfb_picks.py and cfb_card.py will pick this up on the next run. "
          "Nothing to paste.")
except Exception as ex:
    # A failure here must not cost the printed answer above, which is the point
    # of the run. It does have to be loud, because a silent skip would leave the
    # card grading on the previous record while this output says otherwise.
    print(f"  WARNING: could not write model_state.json ({ex})")
    print("  The findings above are correct but the card is still using the "
          "record from the previous run.")
