"""
cfb_card.py — builds the published college football card.

The card makes picks, grades them, and settles them. What it will not do is
turn the size of a disagreement into confidence. Every pick comes from a named
strategy in cfb_picks.py whose tier is computed from its backtested record
against real closing lines, so the card can never claim more than the evidence
supports. As of the last backtest nothing reaches PLAY, one strategy reaches
LEAN, and two are marked AVOID because they backtested as losers.

Sections:
  Picks        the decision table, every game, PLAY LEAN PASS AVOID with a grade
  Slate        the full research detail behind each game
  Cheat sheet  every rated team
  Ledger       how our number compares with the market's, game by game
  Attention    the card checking its own output

Reads data/ written by fetch_data.py and build_ratings.py. Writes docs/, which
GitHub Pages serves.

CFB_MODE says which scheduled run produced this page: rebuild on Sunday morning
once the week is over, refresh every morning, grade every night. The week shown
is always the earliest with unplayed FBS games, so it rolls forward on its own.

Picks are append-only. Once a pick is issued for a game and market it keeps the
number it was issued at, even though the ratings move during the week. A record
that quietly re-prices itself is not a record.
"""
import ast, html, json, math, os, re, sys, zlib
from datetime import datetime, timezone, timedelta
import numpy as np, pandas as pd
from sklearn.linear_model import Ridge
from scipy.stats import norm
import warnings; warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cfb_picks as PICKS
import model_state as MS

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
DOCS = os.path.abspath(os.path.join(BASE, "..", "docs"))
P = lambda f: os.path.join(DATA, f)
os.makedirs(DOCS, exist_ok=True)

MODE = os.environ.get("CFB_MODE", "rebuild").strip().lower()
NOW = datetime.now(timezone.utc)
PHX = NOW - timedelta(hours=7)

# Thresholds come from model_state.json, the same copy the backtest measures
# them against. They were literals here and in cfb_backtest.py, which meant a
# threshold could be tightened in one place and left alone in the other, and
# nothing would fail: the page would simply stop matching its own backtest.
GAME_SD = float(MS.TH["game_sd"])
SPPLUS_FLAG = float(MS.TH["spplus_flag"])
PRICE_FLAG = float(MS.TH["price_flag"])
PRICE_MAX = float(MS.TH["price_max"])
ML_SANE = float(MS.TH["ml_sane"])

# The points model. These moved into the state file when the backtest started
# refitting the same model week by week: it has to use the values the card uses
# or its answer describes a different model.
TOTAL_ALPHA = float(MS.TOTALS["alpha"])
TOTAL_CAP = float(MS.TOTALS["cap"])

# What the last backtest found, for the How to read tab. Written by
# cfb_backtest.py, never typed into this file.
BT = MS.BACKTEST
CAL = BT.get("calibration", {})
HEAD = BT.get("headline", {})


def fail(msg):
    print(f"ERROR: {msg}"); sys.exit(1)


# ------------------------------------------------------------------ load
for need in ("games.csv", "lines.csv", "power_ratings.csv", "meta.json"):
    if not os.path.exists(P(need)):
        fail(f"{need} is missing. Run fetch_data.py and build_ratings.py first.")

META = json.load(open(P("meta.json")))
HFA = float(META.get("hfa", 4.2))
R = pd.read_csv(P("power_ratings.csv")).set_index("team")
REN = {"homeTeam": "home_team", "awayTeam": "away_team", "homePoints": "home_points",
       "awayPoints": "away_points", "neutralSite": "neutral",
       "homeClassification": "home_div", "awayClassification": "away_div",
       "startDate": "start_date"}
frames = []
for f, tag in (("games_prior.csv", "prior"), ("games.csv", "current")):
    if os.path.exists(P(f)):
        d = pd.read_csv(P(f)); d["_src"] = tag; frames.append(d)
G = pd.concat(frames, ignore_index=True).rename(columns=REN)
G["neutral"] = G["neutral"].fillna(False).astype(bool)
G["start_date"] = pd.to_datetime(G.get("start_date"), errors="coerce", utc=True)
CUR = G[G._src == "current"].copy()
PLAYED = G.dropna(subset=["home_points", "away_points"]).copy()


def load_optional(name):
    if not os.path.exists(P(name)):
        return None
    try:
        return pd.read_csv(P(name))
    except Exception as e:
        print(f"  {name} could not be read ({e}); carrying on without it")
        return None


NOTES = {}
if os.path.exists(P("notes.json")):
    try:
        NOTES = json.load(open(P("notes.json")))
        print(f"notes.json: {len(NOTES)} games have notes")
    except Exception as e:
        print(f"notes.json could not be read ({e}); carrying on without it")

SPD = load_optional("sp_ratings.csv")
SP = (SPD.set_index("team")["rating"].astype(float)
      if (SPD is not None and {"team", "rating"}.issubset(SPD.columns)) else pd.Series(dtype=float))
VEN = load_optional("venues.csv")
WX = load_optional("weather.csv")

print(f"mode {MODE}   ratings {len(R)} teams   home field {HFA:+.2f}"
      f"   venues {0 if VEN is None else len(VEN)}   weather {0 if WX is None else len(WX)}")


# ------------------------------------------------------- the totals model
def fit_totals():
    p = PLAYED.copy()
    teams = sorted(set(p.home_team) | set(p.away_team))
    tix = {t: i for i, t in enumerate(teams)}
    n = len(teams)
    maxw = CUR.dropna(subset=["home_points"]).week.max()
    maxw = 0 if pd.isna(maxw) else maxw
    age = np.where(p._src == "current", maxw - p.week, maxw + (15 - p.week))
    w = 0.5 ** (np.asarray(age, dtype=float) / 6.0)
    w = np.where(p._src == "prior", w * 0.55, w)
    m2 = len(p) * 2
    X = np.zeros((m2, 2 * n + 1)); y = np.zeros(m2); ww = np.zeros(m2)
    hi = p.home_team.map(tix).values; ai = p.away_team.map(tix).values
    nz = np.where(p.neutral.values, 0.0, 1.0)
    r = np.arange(len(p))
    X[r, hi] = 1; X[r, n + ai] = 1; X[r, 2 * n] = nz
    y[r] = p.home_points.clip(0, TOTAL_CAP).values; ww[r] = w
    r2 = r + len(p)
    X[r2, ai] = 1; X[r2, n + hi] = 1
    y[r2] = p.away_points.clip(0, TOTAL_CAP).values; ww[r2] = w
    mdl = Ridge(alpha=TOTAL_ALPHA, fit_intercept=True).fit(X, y, sample_weight=ww)
    return (pd.Series(mdl.coef_[:n], index=teams), pd.Series(mdl.coef_[n:2 * n], index=teams),
            float(mdl.coef_[2 * n]), float(mdl.intercept_))


OFF, DEF, HBUMP, MU = fit_totals()
print(f"totals model: league mean {MU:.1f} per team, home bump {HBUMP:+.2f}")


def model_total(home, away, neutral):
    if home not in OFF.index or away not in OFF.index:
        return None
    return float(2 * MU + OFF[home] + DEF[away] + OFF[away] + DEF[home]
                 + (0.0 if neutral else HBUMP))


def model_margin(home, away, neutral):
    if home not in R.index or away not in R.index:
        return None
    return float(R.rating[home] - R.rating[away] + (0.0 if neutral else HFA))


# ------------------------------------------------------------ the market
def parse_books(cell):
    try:
        b = ast.literal_eval(cell)
        return b if isinstance(b, list) else []
    except Exception:
        return []


def med(vals):
    vals = [v for v in vals if v is not None]
    return float(np.median(vals)) if vals else None


def sane_pair(hml, aml):
    """A real two-sided market. Books post -100000 as a placeholder for no
    price, and a median that swallows one of those publishes nonsense."""
    if hml is None or aml is None:
        return False
    if abs(hml) > ML_SANE or abs(aml) > ML_SANE:
        return False
    return not ((hml < 0 and aml < 0) or (hml > 0 and aml > 0))


def ml_to_prob(ml):
    if ml is None:
        return None
    ml = float(ml)
    return 100.0 / (ml + 100.0) if ml > 0 else (-ml) / ((-ml) + 100.0)


def ml_pair_to_spread(hml, aml):
    ph, pa = ml_to_prob(hml), ml_to_prob(aml)
    if ph is None or pa is None or (ph + pa) <= 0:
        return None, None
    p = min(max(ph / (ph + pa), 0.001), 0.999)
    return -(GAME_SD * norm.ppf(p)), p


LINES = pd.read_csv(P("lines.csv"))
LINES["_books"] = LINES["lines"].apply(parse_books)


# ------------------------------------------------- venues, rest and travel
HOME_VENUE = {}
if "venueId" in CUR.columns:
    for t, grp in CUR.dropna(subset=["venueId"]).groupby("home_team"):
        try:
            HOME_VENUE[t] = grp.venueId.mode().iloc[0]
        except Exception:
            pass
VENUE = {}
if VEN is not None and "id" in VEN.columns:
    for _, v in VEN.iterrows():
        VENUE[v["id"]] = v


def haversine(a_lat, a_lon, b_lat, b_lon):
    Rk = 3958.8
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp, dl = p2 - p1, math.radians(b_lon - a_lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * Rk * math.asin(math.sqrt(h))


def travel_miles(away, venue_id):
    hv = HOME_VENUE.get(away)
    if hv is None or venue_id is None or hv not in VENUE or venue_id not in VENUE:
        return None
    a, b = VENUE[hv], VENUE[venue_id]
    try:
        return haversine(float(a["latitude"]), float(a["longitude"]),
                         float(b["latitude"]), float(b["longitude"]))
    except Exception:
        return None


LAST_GAME = {}
for _, g in CUR.dropna(subset=["start_date"]).sort_values("start_date").iterrows():
    for t in (g.home_team, g.away_team):
        LAST_GAME.setdefault(t, []).append(g.start_date)


def rest_days(team, kickoff):
    prior = [d for d in LAST_GAME.get(team, []) if d < kickoff]
    return round((kickoff - max(prior)).total_seconds() / 86400.0) if prior else None


WXI = {}
if WX is not None and "game_id" in WX.columns:
    for _, w in WX.iterrows():
        WXI[w["game_id"]] = w


# --------------------------------------------------------- which week is it
def pick_week():
    unplayed = CUR[CUR.home_points.isna()]
    fbs = unplayed[(unplayed.home_div.str.lower() == "fbs") |
                   (unplayed.away_div.str.lower() == "fbs")]
    if fbs.empty:
        pw = CUR.dropna(subset=["home_points"]).week
        return int(pw.max()) if len(pw) else 1
    return int(fbs.week.min())


WEEK = pick_week()
print(f"card week: {WEEK}")

# ------------------------------------------------------------ build rows
rows = []
global_bad_ml = 0
week_games = CUR[CUR.week == WEEK].copy()
week_games = week_games[(week_games.home_div.str.lower() == "fbs") |
                        (week_games.away_div.str.lower() == "fbs")]
week_games = week_games[(week_games.home_div.str.lower().isin(("fbs", "fcs"))) &
                        (week_games.away_div.str.lower().isin(("fbs", "fcs")))]
week_games = week_games.sort_values("start_date")

line_by_pair = {}
for _, lr in LINES[LINES.week == WEEK].iterrows():
    line_by_pair[(str(lr.awayTeam), str(lr.homeTeam))] = lr

for _, g in week_games.iterrows():
    home, away = str(g.home_team), str(g.away_team)
    final = None
    if pd.notna(g.home_points) and pd.notna(g.away_points):
        final = (int(g.home_points), int(g.away_points))
    hd, ad = str(g.home_div).lower(), str(g.away_div).lower()
    cross = (hd == "fbs") != (ad == "fbs")
    mm = model_margin(home, away, bool(g.neutral))
    mt = model_total(home, away, bool(g.neutral))
    lr = line_by_pair.get((away, home))
    books = lr["_books"] if lr is not None else []

    good_ml = [b for b in books if sane_pair(b.get("homeMoneyline"), b.get("awayMoneyline"))]
    global_bad_ml += sum(1 for b in books
                         if b.get("homeMoneyline") is not None
                         and b.get("awayMoneyline") is not None
                         and not sane_pair(b.get("homeMoneyline"), b.get("awayMoneyline")))
    mkt_spread = med([b.get("spread") for b in books])
    open_spread = med([b.get("spreadOpen") for b in books])
    mkt_total = med([b.get("overUnder") for b in books])
    open_total = med([b.get("overUnderOpen") for b in books])
    mkt_hml = med([b.get("homeMoneyline") for b in good_ml])
    mkt_aml = med([b.get("awayMoneyline") for b in good_ml])

    price_notes = []
    for b in books:
        s, hml, aml = b.get("spread"), b.get("homeMoneyline"), b.get("awayMoneyline")
        if s is None or not sane_pair(hml, aml) or abs(float(s)) > PRICE_MAX:
            continue
        eq, _ = ml_pair_to_spread(hml, aml)
        if eq is None:
            continue
        d = eq - float(s)
        if abs(d) >= PRICE_FLAG:
            price_notes.append(dict(book=str(b.get("provider", "book")), spread=float(s),
                                    equiv=round(eq, 1), diff=round(d, 1)))

    sp_margin = None
    if len(SP) and home in SP.index and away in SP.index:
        sp_margin = float(SP[home] - SP[away] + (0.0 if g.neutral else HFA))
    low_info = (sp_margin is not None and mm is not None and abs(mm - sp_margin) >= SPPLUS_FLAG)

    vid = g.get("venueId")
    vid = None if pd.isna(vid) else vid
    v = VENUE.get(vid)
    wx = WXI.get(g.get("id"))
    kick = g.start_date if pd.notna(g.start_date) else None

    rows.append(dict(
        game_id=g.get("id"), away=away, home=home, cross=cross, neutral=bool(g.neutral),
        final=final, kick=(kick.isoformat() if kick is not None else None),
        model=mm, mkt=(None if mkt_spread is None else -mkt_spread),
        open_mkt=(None if open_spread is None else -open_spread),
        gap=(None if (mm is None or mkt_spread is None) else mm - (-mkt_spread)),
        model_total=mt, mkt_total=mkt_total, open_total=open_total,
        home_ml=mkt_hml, away_ml=mkt_aml,
        home_ml_prob=(ml_pair_to_spread(mkt_hml, mkt_aml)[1]
                      if sane_pair(mkt_hml, mkt_aml) else None),
        sp_margin=sp_margin, low_info=low_info, price=price_notes,
        notes=NOTES.get(f"{away}@{home}"), books=len(books),
        venue=(str(g.get("venue")) if pd.notna(g.get("venue")) else None),
        city=(None if v is None else v.get("city")), state=(None if v is None else v.get("state")),
        dome=(None if v is None else v.get("dome")), grass=(None if v is None else v.get("grass")),
        elevation=(None if v is None else v.get("elevation")),
        temp=(None if wx is None else wx.get("temp_f")),
        wind=(None if wx is None else wx.get("wind_mph")),
        precip=(None if wx is None else wx.get("precip_pct")),
        rest_home=(rest_days(home, kick) if kick is not None else None),
        rest_away=(rest_days(away, kick) if kick is not None else None),
        travel=(travel_miles(away, vid) if not g.neutral else None)))

print(f"games on the card: {len(rows)}  "
      f"({sum(1 for r in rows if not r['cross'])} in scope, "
      f"{sum(1 for r in rows if r['cross'])} cross-division)")

# ------------------------------------------------------------ make picks
PICKS_PATH = os.path.join(DOCS, "picks.csv")
PCOLS = ["season", "week", "away", "home", "market", "strategy", "tier", "grade",
         "side", "number", "book", "issued_utc", "result", "settled_utc"]
pk = pd.read_csv(PICKS_PATH) if os.path.exists(PICKS_PATH) else pd.DataFrame(columns=PCOLS)
for c in PCOLS:
    if c not in pk.columns:
        pk[c] = None
# An all-empty column reads back as float64, and writing "win" into it raises.
# The first settled pick of the season would otherwise crash the nightly run.
for c in ("result", "settled_utc", "tier", "grade", "side", "book",
          "market", "strategy", "away", "home", "issued_utc"):
    pk[c] = pk[c].astype(object)


def _k(v):
    """One spelling for a key field, on both sides of the comparison.

    A pick with no strategy writes an empty cell, which pandas reads back as
    NaN, and NaN never equals NaN. So the guard below could never recognise the
    row it had itself written a run earlier, and appended it again every time.
    Twenty-six moneyline picks were duplicated that way before this was found.
    The card's own self-check did see them, because pandas.duplicated treats
    NaN as equal to NaN while a Python tuple in a set does not: the guard and
    the check were asking the same question two different ways, and the run
    went green. Everything that touches this key now goes through here.
    """
    if v is None or (isinstance(v, float) and v != v):
        return ""
    return str(v).strip()


def pkey(*vals):
    return tuple(_k(v) for v in vals)


# Normalise the key columns on the way in so the stored rows and the rows about
# to be written are spelled the same, then clear out anything the old guard let
# through. Keeping the first copy keeps the number the pick was issued at.
for c in ("season", "week", "away", "home", "market", "strategy", "book"):
    pk[c] = pk[c].map(_k)
_before = len(pk)
pk = pk.drop_duplicates(subset=["season", "week", "away", "home", "market",
                                "strategy", "book"], keep="first").reset_index(drop=True)
PICKS_DEDUPED = _before - len(pk)
if PICKS_DEDUPED:
    print(f"  removed {PICKS_DEDUPED} duplicate picks left by the old guard")
season = int(CUR.season.max()) if "season" in CUR.columns else 0
existing = {pkey(r.season, r.week, r.away, r.home, r.market, r.strategy, r.book)
            for r in pk.itertuples()}
issued = 0
PICKS_BY_GAME = {}
# Measured on this week's own slate rather than quoted from a note: how
# confident the simulation says it is, and how much of the card the fourth gate
# is actually holding back. Both used to be figures typed into the How to read
# text, which meant they described week 1 forever.
SIM_COVERS, UNGATED_A, SPREADS_GRADED = [], 0, 0
for r in rows:
    if r["cross"]:
        PICKS_BY_GAME[(r["away"], r["home"])] = ({}, [])
        continue
    # A pick made after kickoff is not a pick. Grade the game for research, but
    # never write it to the record once it has started or finished.
    started = bool(r["final"])
    if r["kick"]:
        try:
            started = started or datetime.fromisoformat(r["kick"]) <= NOW
        except Exception:
            pass
    # zlib.crc32, not hash(). Python randomises string hashing per process, so
    # hash() gave every run a different seed: the morning refresh and the
    # overnight grade simulated the same game differently and a close call could
    # change sides between them for no reason but noise. Measured over five
    # runs of the unchanged card, four produced different picks. crc32 is a
    # fixed function of the text, so the same game always gets the same draw.
    seed = zlib.crc32(f"{r['away']}|{r['home']}|{WEEK}".encode()) % (2 ** 31)
    mk = PICKS.markets_for(r, WEEK, seed=seed)
    _sp = mk.get("spread")
    if _sp and _sp.get("number") is not None:
        SIM_COVERS.append(float(_sp["p"]))
        SPREADS_GRADED += 1
        if _sp.get("raw") == "A":
            UNGATED_A += 1
    pp = PICKS.price_notes_to_picks(r, r["price"])
    PICKS_BY_GAME[(r["away"], r["home"])] = (mk, pp)
    # Every pick is logged, the way the NFL ledger logs every market. The grade
    # is stored with it so the record can be read grade by grade later.
    entries = [(name, v, "consensus") for name, v in mk.items()]
    entries += [("price", p, p["book"]) for p in pp]
    for market, v, book in entries:
        if v.get("number") is None or started:
            continue
        # .get with a default does not help here: the key is present and its
        # value is None, so the default never applies and None reaches the CSV.
        strat = _k(v.get("strategy"))
        key = pkey(season, WEEK, r["away"], r["home"], market, strat, book)
        if key in existing:
            continue
        pk.loc[len(pk)] = [_k(season), _k(WEEK), r["away"], r["home"], market,
                           strat, v.get("tier", ""), v["grade"],
                           v["side"], v["number"], book, NOW.isoformat(), None, None]
        existing.add(key)
        issued += 1

results = {}
for _, g in CUR.dropna(subset=["home_points", "away_points"]).iterrows():
    results[(int(g.week), str(g.away_team), str(g.home_team))] = (
        int(g.home_points), int(g.away_points))
settled = 0
for i, row in pk.iterrows():
    if isinstance(row.get("result"), str) and row.get("result"):
        continue
    key = (int(row["week"]), str(row["away"]), str(row["home"]))
    if key not in results:
        continue
    hp, ap = results[key]
    outcome = PICKS.settle(str(row["market"]), str(row["side"]), float(row["number"]),
                           str(row["home"]), str(row["away"]), hp, ap)
    if outcome:
        pk.at[i, "result"] = outcome
        pk.at[i, "settled_utc"] = NOW.isoformat()
        settled += 1
pk.to_csv(PICKS_PATH, index=False)
graded = pk[pk.result.isin(["win", "loss", "push"])]
pw = int((graded.result == "win").sum()); pl = int((graded.result == "loss").sum())
pp = int((graded.result == "push").sum())
print(f"picks: {len(pk)} on file, {issued} issued this run, {settled} settled"
      f"   record {pw}-{pl}-{pp}")

# ---------------------------------------------------------------- ledger
LEDGER_PATH = os.path.join(DOCS, "ledger.csv")
ledger = pd.read_csv(LEDGER_PATH) if os.path.exists(LEDGER_PATH) else pd.DataFrame(
    columns=["season", "week", "away", "home", "model", "market", "actual",
             "model_err", "market_err", "closer"])
known = set(zip(ledger.get("season", []), ledger.get("week", []),
                ledger.get("away", []), ledger.get("home", [])))
added = 0
for _, g in CUR.dropna(subset=["home_points", "away_points"]).iterrows():
    home, away = str(g.home_team), str(g.away_team)
    if (season, int(g.week), away, home) in known:
        continue
    if str(g.home_div).lower() != "fbs" or str(g.away_div).lower() != "fbs":
        continue
    lr = None
    for _, x in LINES[LINES.week == g.week].iterrows():
        if str(x.awayTeam) == away and str(x.homeTeam) == home:
            lr = x; break
    mkt = med([b.get("spread") for b in (lr["_books"] if lr is not None else [])])
    mm = model_margin(home, away, bool(g.neutral))
    if mm is None or mkt is None:
        continue
    actual = float(g.home_points - g.away_points)
    me, ke = abs(mm - actual), abs(-mkt - actual)
    ledger.loc[len(ledger)] = [season, int(g.week), away, home, round(mm, 1), round(-mkt, 1),
                               actual, round(me, 1), round(ke, 1),
                               "model" if me < ke else ("market" if ke < me else "tie")]
    added += 1
ledger.to_csv(LEDGER_PATH, index=False)
lw = int((ledger.closer == "model").sum()) if len(ledger) else 0
lt = int((ledger.closer == "market").sum()) if len(ledger) else 0
print(f"ledger: {len(ledger)} games, {added} added, model closer {lw}, market closer {lt}")


# ------------------------------------------------------- self-validation
def check():
    out = []
    fbs_week = week_games[(week_games.home_div.str.lower() == "fbs") &
                          (week_games.away_div.str.lower() == "fbs")]
    shown = {(r["away"], r["home"]) for r in rows}
    for _, g in fbs_week.iterrows():
        if (str(g.away_team), str(g.home_team)) not in shown:
            out.append(("missing game", f"{g.away_team} at {g.home_team} is on the week "
                                        f"{WEEK} schedule but not on the card"))
    seen = {}
    for r in rows:
        seen[(r["away"], r["home"])] = seen.get((r["away"], r["home"]), 0) + 1
    for k, c in seen.items():
        if c > 1:
            out.append(("duplicate", f"{k[0]} at {k[1]} appears {c} times"))
    no_line = [r for r in rows if not r["cross"] and r["mkt"] is None]
    if no_line:
        out.append(("no line", f"{len(no_line)} in-scope games have no posted spread yet: "
                               + ", ".join(f"{r['away']} at {r['home']}" for r in no_line[:6])))
    no_model = [r for r in rows if r["model"] is None]
    if no_model:
        out.append(("unrated team", f"{len(no_model)} games involve a team with no rating"))
    for r in rows:
        if r["model_total"] is not None and not (20 <= r["model_total"] <= 100):
            out.append(("total out of range",
                        f"{r['away']} at {r['home']} projects {r['model_total']:.0f} points"))
    expected = int(META.get("teams", len(R)))
    if abs(len(R) - expected) > 1:
        out.append(("count mismatch",
                    f"power_ratings.csv has {len(R)} teams, meta.json says {expected}"))
    if META.get("fcs_gap", 0) < 15:
        out.append(("gap looks wrong",
                    f"the FBS-over-FCS gap measured {META.get('fcs_gap')} points against a "
                    f"market that prices these near 25. Below 15 usually means the "
                    f"cross-division set is picking up Division II and III games again."))
    if global_bad_ml:
        out.append(("placeholder moneylines",
                    f"{global_bad_ml} book quotes carried an unusable moneyline such as "
                    f"-100000. They were dropped before the consensus was taken."))
    if WX is None or not WXI:
        out.append(("no weather", "no forecast is attached to this week's games. Open-Meteo "
                                  "only reaches about 16 days ahead, and it is best-effort."))
    if VEN is None:
        out.append(("no venues", "venues.csv is missing, so there is no travel distance, "
                                 "surface or elevation on any game."))
    dup = pk.duplicated(subset=["season", "week", "away", "home", "market", "strategy", "book"])
    if len(pk) and dup.any():
        out.append(("duplicate picks", f"{int(dup.sum())} picks are recorded twice. The "
                                       f"append-only guard is not holding."))
    if PICKS_DEDUPED:
        out.append(("picks cleaned", f"{PICKS_DEDUPED} duplicate picks were removed from "
                                     f"picks.csv. They were written by a guard that could "
                                     f"not recognise a pick with no strategy, and the "
                                     f"earliest copy of each was kept."))
    if MS.FELL_BACK:
        out.append(("state file", f"{MS.FELL_BACK}, so every constant and backtest figure "
                                  f"on this page came from the copy compiled into "
                                  f"model_state.py. The card still built, but it is quoting "
                                  f"the values as they stood when that file was written, "
                                  f"not whatever the JSON was meant to say."))
    if not BT.get("run_utc"):
        out.append(("backtest date", "model_state.json does not record when the backtest "
                                     "behind these grades was run."))
    if not rows:
        out.append(("empty card", f"no games found for week {WEEK}"))
    return out


ISSUES = check()
print(f"self-check: {len(ISSUES)} things to flag")
for kind, msg in ISSUES:
    print(f"  {kind}: {msg}")


# ---------------------------------------------------------------- render
def esc(x):
    return html.escape(str(x))


def num(v):
    """A number is only a number if it is finite. Everything else is a dash."""
    try:
        f = float(v)
        return f if np.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def fmt(v, plus=False, nd=1):
    f = num(v)
    if f is None:
        return "&mdash;"
    return f"{f:+.{nd}f}" if plus else f"{f:.{nd}f}"


def phx(iso):
    if not iso:
        return ""
    try:
        return (datetime.fromisoformat(iso) - timedelta(hours=7)).strftime("%a %-d %b, %-I:%M %p")
    except Exception:
        return ""


def spread_label(r):
    if r["model"] is None:
        return "&mdash;"
    m = r["model"]
    fav, n2 = (r["home"], -m) if m > 0 else (r["away"], m)
    return f"{esc(fav)} {n2:+.1f}"


TC = {"PLAY": "play", "LEAN": "lean", "PASS": "pass", "AVOID": "avoid"}


def fmtnum(market, n):
    if n is None:
        return ""
    if market == "moneyline":
        return f"{int(n):+d}"
    if market == "total":
        return f"{n:.1f}"
    return f"{n:+.1f}"



def what_this_tells_you(r, mk, pp):
    """The NFL card's last column: what is odd about this game, if anything."""
    notes = []
    if pp:
        p = max(pp, key=lambda x: abs(x["number"]))
        notes.append(p["reason"])
    sp, ml = mk.get("spread"), mk.get("moneyline")
    if sp and ml and sp["side"] != ml["side"]:
        notes.append(f"Markets point different ways. Best cover is {sp['side']} "
                     f"({100*sp['p']:.1f}% to cover). Best value to win outright is "
                     f"{ml['side']}, we make them {100*ml['p']:.1f}% and the price implies "
                     f"{100*(ml['p'] - ml['edge']/100):.1f}%.")
    if r["low_info"] and r["sp_margin"] is not None and r["model"] is not None:
        notes.append(f"Our two models disagree by {abs(r['model']-r['sp_margin']):.1f} points: "
                     f"ours has {r['model']:+.1f}, SP+ has {r['sp_margin']:+.1f}. "
                     f"Low-information game.")
    return " ".join(notes) if notes else "nothing unusual"


def summary_table():
    body = []
    for r in rows:
        if r["cross"] or r["final"]:
            continue
        mk, pp = PICKS_BY_GAME.get((r["away"], r["home"]), ({}, []))
        sp, ml, tt = mk.get("spread"), mk.get("moneyline"), mk.get("total")
        def cell(v, fmtnum=lambda n: f"{n:+.1f}"):
            """The call, then confidence and value side by side, then the merge.

            Two readings rather than one, because they answer different
            questions and the model is far better at one of them. Confidence is
            how likely this is to happen. Value is whether the price pays for
            it. The merged letter is the two weighted together.
            """
            if v is None or v.get("number") is None:
                return ('<td>&mdash;</td><td class="gr">&mdash;</td>'
                        '<td class="gr">&mdash;</td><td class="gr">&mdash;</td>')
            star = '<span class="cap" title="' + esc(v.get("capped") or "") + '">*</span>' \
                   if v.get("capped") else ""
            tip = esc(f"confidence {v.get('conf_pct', 0):.1f}% against a break-even of "
                      f"{v.get('break_even', 0):.1f}%, so {v.get('margin_pp', 0):+.1f} points "
                      f"of value. {v.get('calibration', '')}")
            return (f'<td>{esc(v["side"])} {fmtnum(v["number"])}</td>'
                    f'<td class="gr g{v.get("conf","D")}" title="{tip}">{v.get("conf","D")}'
                    f'<span class="pct">{v.get("conf_pct", 0):.0f}%</span></td>'
                    f'<td class="gr g{v.get("value","D")}" title="{tip}">{v.get("value","D")}'
                    f'<span class="pct">{v.get("margin_pp", 0):+.1f}</span></td>'
                    f'<td class="gr g{v["grade"]}" title="{tip}">{v["grade"]}{star}</td>')
        kick = phx(r["kick"])
        best = PICKS.best_of(mk, pp)
        if best:
            bg, bmk, bv = best
            bnum = fmtnum("moneyline" if bmk == "moneyline" else
                          ("total" if bmk == "total" else "spread"), bv.get("number"))
            bcell = (f'<td class="gr g{bg}">{bg}</td>'
                     f'<td>{esc(bv["side"])} {bnum}'
                     + (f' <span class="bk">{esc(bv["book"])}</span>'
                        if bv.get("book") and bv["book"] != "consensus" else '') + '</td>')
        else:
            bcell = '<td class="gr">&mdash;</td><td>&mdash;</td>'
        body.append(
            f'<tr><td>{esc(kick)}</td><td>{esc(r["away"])} at {esc(r["home"])}</td>'
            + bcell
            + cell(sp)
            + cell(ml, lambda n: f"{int(n):+d}")
            + cell(tt, lambda n: f"{n:.1f}")
            + f'<td class="wtt">{esc(what_this_tells_you(r, mk, pp))}</td></tr>')
    if not body:
        return '<p class="muted">No in-scope games left to play this week.</p>'
    return ('<div class="scroll"><table class="sheet sum"><thead><tr>'
            '<th>day / time</th><th>game</th><th>best</th><th>the call</th>'
            '<th>spread</th><th>conf</th><th>value</th><th>grade</th>'
            '<th>moneyline</th><th>conf</th><th>value</th><th>grade</th>'
            '<th>total</th><th>conf</th><th>value</th><th>grade</th>'
            '<th>what this tells you</th></tr></thead><tbody>'
            + "".join(body) + '</tbody></table></div>'
            '<p class="muted"><b>conf</b> is how likely the call is to happen, after the '
            'backtest has corrected what the model claims. <b>value</b> is how far that '
            'sits above the break-even the price demands. <b>grade</b> is the two '
            'weighted together. Hover any of them for the working. A star means the '
            'grade was capped.</p>')


def strategy_table():
    out = []
    for s in PICKS.RECORD:
        tier, pct, (lo, hi), n = PICKS.tier_of(s)
        live = pk[(pk.strategy == s) & pk.result.isin(["win", "loss", "push"])] if len(pk) else pk
        lwin = int((live.result == "win").sum()) if len(live) else 0
        lloss = int((live.result == "loss").sum()) if len(live) else 0
        out.append(f'<tr><td>{esc(s.replace("_", " "))}</td>'
                   f'<td><span class="tier {TC.get(tier,"pass")}">{tier}</span></td>'
                   f'<td>{pct:.1f}%</td>'
                   f'<td>{lo:.1f} to {hi:.1f}</td><td>{n:,}</td><td>{lwin}-{lloss}</td></tr>')
    return ('<table class="sheet"><thead><tr><th>strategy</th><th>call</th>'
            '<th>backtest</th><th>95% interval</th><th>games</th><th>live 2026</th>'
            '</tr></thead><tbody>' + "".join(out) + "</tbody></table>")


def picks_ledger():
    if not len(pk):
        return ('<p class="muted">No picks issued yet. Picks are only written before '
                'kickoff, so a slate that has already played adds no rows.</p>')
    done = pk[pk.result.isin(["win", "loss", "push"])]
    by_grade = ""
    if len(done):
        rowsg = []
        for gl in ("A", "B", "C", "D"):
            sub = done[done.grade == gl]
            if not len(sub):
                continue
            w = int((sub.result == "win").sum()); l = int((sub.result == "loss").sum())
            pct = 100 * w / max(w + l, 1)
            rowsg.append(f"<tr><td>{gl}</td><td>{w}-{l}</td><td>{pct:.1f}%</td>"
                         f"<td>{len(sub)}</td></tr>")
        by_grade = ('<h2>Does the grade discriminate?</h2>'
                    '<p class="muted">If the grading works, A should beat B should beat C. '
                    'This table is the only honest test of it, and it needs a season to '
                    'mean anything.</p>'
                    '<table class="sheet"><thead><tr><th>grade</th><th>record</th>'
                    '<th>win%</th><th>picks</th></tr></thead><tbody>'
                    + "".join(rowsg) + "</tbody></table>")
    d = pk.sort_values(["week"], ascending=False).head(400)
    body = "".join(
        f'<tr><td>{int(x.week)}</td><td>{esc(x.away)} at {esc(x.home)}</td>'
        f'<td>{esc(x.market)}</td><td>{esc(x.side)} {fmtnum(str(x.market), float(x.number))}</td>'
        f'<td>{esc(x.book)}</td><td class="gr g{esc(x.grade)}">{esc(x.grade)}</td>'
        f'<td class="{esc(x.result) if isinstance(x.result, str) else ""}">'
        f'{esc(x.result) if isinstance(x.result, str) else "pending"}</td></tr>'
        for x in d.itertuples())
    return (by_grade + f'<h2>Every pick issued</h2><p>{pw} wins, {pl} losses, {pp} pushes '
            f'on settled picks.</p>'
            '<div class="scroll"><table class="sheet"><thead><tr><th>wk</th><th>game</th>'
            '<th>market</th><th>pick</th><th>book</th><th>grade</th><th>result</th>'
            '</tr></thead><tbody>' + body + "</tbody></table></div>")


def research(r):
    bits = []
    if r["venue"]:
        place = r["venue"]
        if isinstance(r["city"], str):
            place += f", {r['city']}"
            if isinstance(r["state"], str):
                place += f" {r['state']}"
        extra = []
        if str(r["dome"]).lower() == "true":
            extra.append("indoors")
        if str(r["grass"]).lower() == "true":
            extra.append("grass")
        elif str(r["grass"]).lower() == "false":
            extra.append("turf")
        el = num(r["elevation"])
        if el is not None and el > 3000:
            extra.append(f"{el:.0f} ft elevation")
        if r["neutral"]:
            extra.append("neutral site")
        bits.append(("venue", place + (" (" + ", ".join(extra) + ")" if extra else "")))
    t, wnd, pr = num(r["temp"]), num(r["wind"]), num(r["precip"])
    if t is not None:
        w = f"{t:.0f}F"
        if wnd is not None:
            w += f", wind {wnd:.0f} mph"
        if pr is not None:
            w += f", {pr:.0f}% chance of rain"
        bits.append(("weather at kickoff", w))
    rest = []
    for team, key in ((r["home"], "rest_home"), (r["away"], "rest_away")):
        if r[key] is not None:
            rest.append(f"{team} {int(r[key])} days")
    if rest:
        bits.append(("rest", ", ".join(rest)))
    tv = num(r["travel"])
    if tv:
        bits.append(("travel", f"{r['away']} travels {tv:.0f} miles"))
    move = []
    if r["open_mkt"] is not None and r["mkt"] is not None:
        d = r["mkt"] - r["open_mkt"]
        move.append(f"spread opened {-r['open_mkt']:+.1f}, now {-r['mkt']:+.1f}"
                    + (f", {abs(d):.1f} toward {r['home'] if d > 0 else r['away']}"
                       if abs(d) >= 0.5 else ", unmoved"))
    if r["open_total"] is not None and r["mkt_total"] is not None:
        dt = r["mkt_total"] - r["open_total"]
        move.append(f"total opened {r['open_total']:.1f}, now {r['mkt_total']:.1f}"
                    + (f", {dt:+.1f}" if abs(dt) >= 0.5 else ""))
    if move:
        bits.append(("line movement", "; ".join(move)))
    for team, label in ((r["home"], "home"), (r["away"], "away")):
        d = []
        if team in R.index:
            row = R.loc[team]
            rk = num(row.get("rank"))
            if rk is not None:
                d.append(f"#{int(rk)} overall")
            for col, name in (("talent", "talent"), ("sp_rating", "SP+"),
                              ("sp_offense.rating", "SP+ offense"),
                              ("sp_defense.rating", "SP+ defense"),
                              ("ret_percentPPA", "returning production")):
                v = num(row.get(col)) if col in R.columns else None
                if v is not None:
                    d.append(f"{name} {v:.0f}" if abs(v) > 10 else f"{name} {v:.2f}")
        if d:
            bits.append((f"{team} ({label})", ", ".join(d)))
    if r["home_ml_prob"] is not None:
        bits.append(("market win probability",
                     f"{r['home']} {100*r['home_ml_prob']:.0f}%, "
                     f"{r['away']} {100*(1-r['home_ml_prob']):.0f}%, vig removed"))
    if r["price"]:
        bits.append(("price consistency", "; ".join(
            f"{p['book']} posts {p['spread']:+.1f}, its moneyline implies {p['equiv']:+.1f}"
            for p in r["price"])))
    if r["notes"]:
        for k, v in r["notes"].items():
            if not v:
                continue
            bits.append((k, ", ".join(map(str, v)) if isinstance(v, list) else str(v)))
    if not bits:
        return ""
    return ('<div class="rs"><div class="ph">Research</div>'
            + "".join(f'<div class="nn"><span>{esc(k)}</span> {esc(v)}</div>' for k, v in bits)
            + "</div>")


def game_card(r):
    if r["final"]:
        hp, ap = r["final"]
        actual = hp - ap
        verdict = ""
        if r["model"] is not None and r["mkt"] is not None:
            me, ke = abs(r["model"] - actual), abs(r["mkt"] - actual)
            who = ("Our number was closer" if me < ke else
                   "The market was closer" if ke < me else "Both missed by the same")
            verdict = (f"Final margin {actual:+d}. We said {r['model']:+.1f}, the market said "
                       f"{r['mkt']:+.1f}. {who}, by {abs(me - ke):.1f}.")
        mine = pk[(pk.away == r["away"]) & (pk.home == r["home"])] if len(pk) else pk
        ptxt = ""
        if len(mine):
            ptxt = ('<div class="price-box"><div class="ph">Our picks</div>' + "".join(
                f'<div class="pn">{esc(x.side)} {float(x.number):+.1f} at {esc(x.book)}: '
                f'<b>{esc(x.result) if isinstance(x.result, str) else "pending"}</b></div>'
                for x in mine.itertuples()) + "</div>")
        return f'''
<article class="game final{' cross' if r['cross'] else ''}">
  <header><h3>{esc(r['away'])} at {esc(r['home'])}</h3><span class="tag done">final</span></header>
  <div class="score">{esc(r['home'])} {hp}, {esc(r['away'])} {ap}</div>
  <div class="gap muted">{esc(verdict)}</div>{ptxt}
</article>'''

    mk, pp = PICKS_BY_GAME.get((r["away"], r["home"]), ({}, []))
    best = PICKS.best_of(mk, pp)
    tag = ('<span class="tag out">out of scope</span>' if r["cross"] else
           (f'<span class="tier g{best[0]}">{best[0]}</span>' if best else ''))
    if r["low_info"]:
        tag += '<span class="tag warn">low information</span>'
    callbox = ""
    entries = [(name, v) for name, v in mk.items()] + [("price", p) for p in pp]
    if entries:
        callbox = '<div class="calls">' + "".join(
            f'<div class="call g{v["grade"]}">'
            f'<b>{v["grade"]}</b> &middot; {esc(name)} &middot; {esc(v["side"])} '
            f'{fmtnum(name, v.get("number"))}'
            f'<div class="why">{esc(v.get("reason") or "")}</div>'
            f'<div class="ev">wins {100*v["p"]:.1f}% of 20,000 runs, '
            f'{v["edge"]:.1f} points of value, NFL-style score {v["score"]}'
            f'{" (capped: " + esc(v["capped"]) + ")" if v.get("capped") else ""}. '
            f'{esc(v.get("evidence") or "")}</div></div>'
            for name, v in entries) + "</div>"
    gaprow = ('<div class="gap muted">Cross-division. The model cannot place FBS and FCS on '
              'one reliable scale, so this game gets no pick.</div>') if r["cross"] else ""
    sp = "&mdash;" if r["sp_margin"] is None else fmt(r["sp_margin"], plus=True)
    ml = "&mdash;"
    if r["home_ml"] is not None and r["away_ml"] is not None:
        ml = f'{esc(r["home"])} {int(r["home_ml"]):+d} / {esc(r["away"])} {int(r["away_ml"]):+d}'
    return f"""
<article class="game{' cross' if r['cross'] else ''}">
  <header><h3>{esc(r['away'])} at {esc(r['home'])}</h3>
  <div class="kick">{esc(phx(r['kick']))} Phoenix</div>{tag}</header>
  <table class="nums">
    <tr><th></th><th>our number</th><th>the market</th></tr>
    <tr><td>spread</td><td>{spread_label(r)}</td>
        <td>{'&mdash;' if r['mkt'] is None else esc(f"{r['home']} {-r['mkt']:+.1f}")}</td></tr>
    <tr><td>total</td><td>{fmt(r['model_total'])}</td><td>{fmt(r['mkt_total'])}</td></tr>
    <tr><td>SP+ cross-check</td><td colspan="2">{sp}{' &nbsp; diverges from our number' if r['low_info'] else ''}</td></tr>
    <tr><td>moneyline</td><td colspan="2">{ml}</td></tr>
  </table>
  {callbox}{gaprow}{research(r)}
</article>"""


def cheat_sheet():
    d = R.reset_index()
    cols = [c for c in ("rank", "team", "rating", "talent_prior", "form", "conference",
                        "division") if c in d.columns]
    d = d[cols]
    head = "".join(f"<th>{esc(c.replace('_',' '))}</th>" for c in cols)
    body = "".join("<tr>" + "".join(
        f"<td>{esc(round(v,2) if isinstance(v,float) else v)}</td>" for v in row) + "</tr>"
        for row in d.itertuples(index=False))
    return f'<table class="sheet"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def accuracy_ledger():
    if not len(ledger):
        return '<p class="muted">Nothing here yet. Rows appear as games finish.</p>'
    d = ledger.sort_values(["week"], ascending=False)
    body = "".join(
        f"<tr><td>{int(x.week)}</td><td>{esc(x.away)} at {esc(x.home)}</td>"
        f"<td>{x.model:+.1f}</td><td>{x.market:+.1f}</td><td>{x.actual:+.0f}</td>"
        f"<td>{x.model_err:.1f}</td><td>{x.market_err:.1f}</td>"
        f'<td class="{esc(x.closer)}">{esc(x.closer)}</td></tr>' for x in d.itertuples())
    return (f"<p>Across {len(ledger)} completed games, our number missed the final margin by "
            f"<b>{ledger.model_err.mean():.1f}</b> points on average and the market's by "
            f"<b>{ledger.market_err.mean():.1f}</b>. We were closer in <b>{lw}</b>, "
            f"the market in <b>{lt}</b>.</p>"
            '<table class="sheet"><thead><tr><th>wk</th><th>game</th><th>ours</th>'
            '<th>market</th><th>actual</th><th>our miss</th><th>their miss</th>'
            '<th>closer</th></tr></thead><tbody>' + body + "</tbody></table>")


def how_to_read():
    a, b, base = PICKS.TOTAL_TILT
    MED_COVER = 100 * float(np.median(SIM_COVERS)) if SIM_COVERS else 0.0
    return f"""
<h2>Two grades, not one</h2>
<p>Every market gets two readings, because they answer different questions and this model is
far better at one of them.</p>
<table class="sheet"><tbody>
<tr><td><b>Confidence</b></td>
<td>How likely the call is to happen. Nothing to do with the price. The simulation's answer,
corrected by what calls like it actually did over {BT.get('window', 'the backtest window')}.
Bands: A at {PICKS.CONF_A:.0f}% or better, B at {PICKS.CONF_B:.0f}%, C at {PICKS.CONF_C:.0f}%,
D below.</td></tr>
<tr><td><b>Value</b></td>
<td>How far that corrected probability sits above the break-even the price demands. A spread
or total carries no price in this feed, so it uses the standard {PICKS.BREAK_EVEN}% figure. A
moneyline has a real price and uses it. Bands: A at {PICKS.VALUE_A:+.0f} points or better,
B at {PICKS.VALUE_B:+.0f}, C at break-even, D below.</td></tr>
<tr><td><b>Grade</b></td>
<td>The two weighted together, confidence {100*PICKS.W_CONF:.0f}% and value
{100*PICKS.W_VALUE:.0f}%. Those weights are the only chosen numbers in the scheme. They sit
in model_state.json next to the measured ones so it is obvious which is which.</td></tr>
</tbody></table>
<p><b>Why two and not the old single score.</b> The old grade was one score out of 100, seventy
points for the win probability and thirty for value over the price. On a spread or a total
that was one number counted twice: the feed carries the number and no price, so the market's
implied probability is fifty percent by construction and the value term was the win
probability restated. The moneyline was the only market where the two were genuinely
different. Splitting them makes that visible instead of hiding it inside an average.</p>

<h2>Why a simulated probability is not a probability</h2>
<p>The simulation says what would happen if our number were right. Whether it is right is a
separate question, and the backtest answers it by fitting, for each market, the line that
maps what the model claimed onto what actually happened.</p>
<table class="sheet"><thead><tr><th>market</th><th>what the fit says</th></tr></thead><tbody>
{"".join(f'<tr><td>{esc(k.replace("_"," "))}</td><td>{esc(PICKS.calibration_note(k))}</td></tr>' for k in ("outright", "model_gap_early", "model_gap_late", "total_model", "price_gap") if isinstance(CAL.get(k), dict))}
</tbody></table>
<p>Read that table before reading any grade. <b>Predicting the winner works. Beating the
number does not.</b> The outright fit clears zero comfortably, so moneyline confidence means
something. The spread and total slopes cannot be told apart from zero, which is why their
confidence sits near a coin flip however far our number is from the market's. That is the
measurement, not a decision.</p>
<p>One thing worth knowing from the same fit: when the model calls a game close to even, the
home team actually wins about 45% of the time. The model over-rates home teams in tight
games, so road teams in near-even matchups are underrated by roughly the same amount.</p>

<h2>What caps a grade</h2>
<p>A star means the grade was held back, and hovering it says why. Three things can do it.</p>
<p><b>A strategy that backtested below break-even</b> cannot grade above C, whatever the
simulation says. <b>A market with no backtested record</b> cannot grade above B: confidence
may be measured, but whether betting it makes money has never been tested, and an A would
claim it had been. <b>A market that has never been calibrated</b> cannot grade above C,
because an unchecked probability is a claim about nothing.</p>
<p>Every cap lifts on its own. Re-running the cfb-backtest workflow writes the new record and
the new calibration into model_state.json, and every grade here recalculates with nothing to
paste. Every number on this tab is read from that file, so the page cannot drift away from
the backtest it is quoting. This one was run on {esc(BT.get('run_utc', 'an unrecorded date'))}
over {esc(BT.get('window', 'an unrecorded window'))}.</p>
<p class="muted">For reference, the old single score is still computed on every game. On this
week's slate it would have graded {UNGATED_A} of {SPREADS_GRADED} spreads an A, on a strategy
that backtested below break-even.</p>

<h2>The simulation</h2>
<p>Every game runs {PICKS.SIMS:,} times rather than through a single formula. Each run makes
two draws.</p>
<table class="sheet"><tbody>
<tr><td><b>Our own uncertainty</b></td><td>We do not know the true line, only our estimate.
Each run pulls a true line from a distribution centred on our number with a
{PICKS.LINE_SD:.1f}-point spread. The NFL card uses 3.0. Ours is more than double because
that is what the data says: the standard deviation of our number minus the market's is
{PICKS.LINE_SD:.1f} points.</td></tr>
<tr><td><b>The game itself</b></td><td>Given that line, the margin is drawn with a standard
deviation of about {PICKS.MARGIN_SD:.1f} points, against the NFL's 13.2, widening for high
totals and tightening for low ones. Totals are drawn separately at {PICKS.TOTAL_SD:.1f}
points, against the NFL's 10.4.</td></tr>
</tbody></table>
<p class="muted">The margin tilt is fitted, not assumed: absolute residual =
{a:.4f} x total + {b:.2f} over 762 FBS games from 2025, normalised at a total of 52. Wind is
not adjusted for, because there is no historical college weather on hand to measure it.</p>

<h2>What this tells you</h2>
<table class="sheet"><tbody>
<tr><td><b>A book's two prices disagree</b></td><td>Its moneyline implies a different spread
than the one it posts, so one is stale. Names the better-priced ticket. Says nothing about
which side to take. This is the only angle here that needs no model, and the only one
currently rated better than AVOID.</td></tr>
<tr><td><b>Markets point different ways</b></td><td>The best cover and the best value to win
outright are different teams. Legitimate: a team can be likely to win without winning by the
number.</td></tr>
<tr><td><b>Our two models disagree</b></td><td>Our ridge rating against SP+. Past 10 points
apart, one is badly wrong with no way to tell which. Low information.</td></tr>
<tr><td><b>nothing unusual</b></td><td>No pricing inconsistency, no split between markets,
no model disagreement.</td></tr>
</tbody></table>

<h2>Where the numbers come from</h2>
<p>Power ratings are an opponent-adjusted ridge regression on game margins, shrunk toward a
recruiting-talent prior. Games, lines, talent, SP+, returning production and venues come from
CollegeFootballData; weather from Open-Meteo. Injuries, transfers, coaching changes and
expert picks are in no dataset and are researched separately into notes.json.</p>
<p>Scope is FBS and FCS. Cross-division games are shown for reference and never given a pick,
because a single offset cannot place the two divisions on one reliable scale.</p>
"""


# Each entry is (level, title, why it matters, what to do). The NFL card shows
# problems this way and it is a better shape: a title alone does not tell you
# whether the page can be trusted or what to do next.
FIXES = {
    "missing game": ("WARN", "A scheduled game is not on the card",
                     "Refetch the schedule and rebuild. If it persists the team name is not matching between files."),
    "duplicate": ("ERROR", "The same game is rendered more than once",
                  "The dedupe on the games frame is not holding. Do not trust the counts on this page."),
    "no line": ("INFO", "Some games have no posted spread yet",
                "No action. Books post college numbers late in the week and the next refresh picks them up."),
    "unrated team": ("WARN", "A team on the card has no rating",
                     "Usually a team below the minimum games threshold. It resolves as the season fills in."),
    "total out of range": ("WARN", "A projected total is outside a sane range",
                           "Check the points model on that game before using the total."),
    "count mismatch": ("ERROR", "The ratings file and the run summary disagree on team count",
                       "Rebuild the ratings. The two files were written by different runs."),
    "gap looks wrong": ("ERROR", "The FBS over FCS gap is outside what the market implies",
                        "The cross-division set is picking up Division II and III again. See do not reintroduce (b)."),
    "placeholder moneylines": ("INFO", "Some book prices were placeholders and were dropped",
                               "No action. Some books post -100000 to mean no price, and those are removed."),
    "no weather": ("INFO", "No weather forecast is attached",
                   "No action. Open-Meteo only reaches about two weeks out and weather is best-effort."),
    "no venues": ("INFO", "Venue detail is missing",
                  "Refetch. Without it there is no travel distance, surface or elevation."),
    "picks cleaned": ("INFO", "Duplicate picks were removed from the record",
                      "No action. The guard that let them through is fixed; the count should be zero from now on."),
    "duplicate picks": ("ERROR", "A pick is recorded twice",
                        "The append-only guard is not holding. Check picks.csv before trusting the record."),
    "state file": ("ERROR", "The state file could not be read",
                   "Every number on this page came from the fallback copy. Fix scripts/model_state.json."),
    "backtest date": ("WARN", "The backtest behind these grades is undated",
                      "Re-run the cfb-backtest workflow so the record carries a date."),
    "empty card": ("ERROR", "No games found for this week",
                   "The week selector or the schedule pull is wrong. Nothing on this page is usable."),
}
LVL = {"ERROR": "fl", "WARN": "c", "INFO": "b"}


def issues_html():
    if not ISSUES:
        return '<div class="card"><b>Nothing to flag.</b> Every self-check passed.</div>'
    out = []
    for kind, msg in ISSUES:
        lvl, title, fix = FIXES.get(kind, ("WARN", kind.title(), "No fix recorded."))
        out.append(
            f'<div class="card lv{LVL[lvl]}">'
            f'<div class="lvl"><span class="tag t{LVL[lvl]}">{lvl}</span> {esc(title)}</div>'
            f'<div class="why"><b>Why it matters:</b> {esc(msg)}</div>'
            f'<div class="fix"><b>Fix:</b> {esc(fix)}</div></div>')
    return "".join(out)


SEASON_TXT = f"{int(CUR.season.max()) if 'season' in CUR.columns and len(CUR) else ''} season".strip()
in_scope = [r for r in rows if not r["cross"] and not r["final"]]
cross_rows = [r for r in rows if r["cross"] and not r["final"]]
final_rows = [r for r in rows if r["final"]]
grades = []
for r in in_scope:
    mk, pp = PICKS_BY_GAME.get((r["away"], r["home"]), ({}, []))
    b = PICKS.best_of(mk, pp)
    if b:
        grades.append(b[0])
n_a = grades.count("A")
n_b = grades.count("B")

HTML = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>College card &middot; week {WEEK}</title>
<style>
:root {{ --ink:#12161c; --mute:#5d6875; --line:#dce1e7; --bg:#fbfcfd; --pan:#ffffff;
--hd:#f4f6f8; --hov:#f8fafb; --a:#0d7a4f; --abg:#e8f5ee; --b:#1a5f9e; --bbg:#e7f0f9;
--c:#7a6a1a; --cbg:#f7f2df; --n:#8b95a1; --nbg:#f1f3f5; --fl:#a8541a; --flbg:#fdf0e4;
--sp:#553a7a; --spbg:#efe7f7; --sep:#aab4c0; }}
body.dark {{ --ink:#e6eaf0; --mute:#9aa5b3; --line:#2b333d; --bg:#12161c; --pan:#1a1f27;
--hd:#222833; --hov:#20262f; --a:#4ade80; --abg:#12321f; --b:#7cb8f0; --bbg:#0f2740;
--c:#e0c766; --cbg:#332c12; --n:#8b95a1; --nbg:#252b34; --fl:#e0913f; --flbg:#3a2712;
--sp:#c4a8ee; --spbg:#2c2140; --sep:#5a6675; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; padding:26px 18px 70px; background:var(--bg); color:var(--ink);
transition:background .15s; font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",
Helvetica,Arial,sans-serif; }}
.wrap {{ max-width:1280px; margin:0 auto; }}
.top {{ display:flex; align-items:center; gap:14px; flex-wrap:wrap; }}
h1 {{ font-size:25px; margin:0; letter-spacing:-.01em; }}
h2 {{ font-size:13px; text-transform:uppercase; letter-spacing:.09em; color:var(--mute);
margin:30px 0 11px; padding-bottom:6px; border-bottom:1px solid var(--line);
font-weight:600; scroll-margin-top:60px; }}
h3 {{ font-size:14px; margin:20px 0 8px; }}
.sub {{ color:var(--mute); font-size:13px; margin-bottom:18px; }}
.nav {{ position:sticky; top:0; z-index:20; background:var(--bg); padding:8px 0 10px;
margin-bottom:6px; border-bottom:1px solid var(--line); display:flex; gap:8px; flex-wrap:wrap; }}
.nav a {{ font-size:12px; padding:4px 10px; border:1px solid var(--line); border-radius:20px;
color:var(--mute); text-decoration:none; background:var(--pan); }}
.nav a:hover {{ background:var(--hov); color:var(--ink); }}
.toggle {{ margin-left:auto; font-size:12px; padding:5px 12px; border:1px solid var(--line);
border-radius:20px; background:var(--pan); color:var(--mute); cursor:pointer; }}
.card {{ background:var(--pan); border:1px solid var(--line); border-radius:8px;
padding:13px 15px; margin-bottom:10px; }}
.lvfl {{ border-left:3px solid var(--fl); }}
.lvc {{ border-left:3px solid var(--c); }}
.lvb {{ border-left:3px solid var(--b); }}
.lvl {{ font-weight:600; margin-bottom:6px; }}
.why {{ font-size:13px; color:var(--mute); margin-bottom:6px; }}
.fix {{ font-size:13px; background:var(--flbg); color:var(--fl); display:inline-block;
padding:3px 8px; border-radius:5px; }}
.tag {{ display:inline-block; padding:2px 7px; border-radius:10px; font-size:10.5px;
font-weight:600; }}
.tfl {{ background:var(--flbg); color:var(--fl); }}
.tc {{ background:var(--cbg); color:var(--c); }}
.tb {{ background:var(--bbg); color:var(--b); }}
table {{ border-collapse:collapse; width:100%; font-size:12.5px; }}
th {{ background:var(--hd); text-align:left; padding:8px 9px; font-weight:600; font-size:10.5px;
text-transform:uppercase; letter-spacing:.05em; color:var(--mute);
border-bottom:1px solid var(--line); white-space:nowrap; }}
td {{ padding:8px 9px; border-bottom:1px solid var(--line); white-space:nowrap; }}
tbody tr:hover {{ background:var(--hov); }}
.wtt {{ white-space:normal; font-size:12px; min-width:230px; line-height:1.4; color:var(--mute); }}
.grp {{ border-left:1px solid var(--line); }}
.num {{ color:var(--mute); font-variant-numeric:tabular-nums; }}
.scroll {{ overflow-x:auto; border:1px solid var(--line); border-radius:8px; }}
.gr {{ font-weight:700; text-align:center; }}
.gA {{ color:var(--a); }} .gB {{ color:var(--b); }} .gC {{ color:var(--c); }} .gD {{ color:var(--n); }}
.pct {{ display:block; font-size:10px; font-weight:400; opacity:.75; }}
.cap {{ color:var(--fl); cursor:help; }}
.bk {{ color:var(--mute); font-size:11px; }}
.muted {{ color:var(--mute); font-size:12.5px; }}
.ok {{ color:var(--a); }}
.tier {{ display:inline-block; padding:2px 7px; border-radius:10px; font-size:10.5px;
font-weight:600; background:var(--nbg); color:var(--n); }}
.tier.play {{ background:var(--abg); color:var(--a); }}
.tier.lean {{ background:var(--bbg); color:var(--b); }}
.tier.avoid {{ background:var(--flbg); color:var(--fl); }}
article.game {{ background:var(--pan); border:1px solid var(--line); border-radius:10px;
padding:14px 16px; margin-bottom:10px; }}
article.game.cross {{ opacity:.75; }}
article.game h3 {{ margin:0 0 8px; }}
.banner {{ background:var(--pan); border:1px solid var(--line); border-left:3px solid var(--b);
border-radius:8px; padding:13px 15px; margin-bottom:16px; font-size:13.5px; }}
footer {{ color:var(--mute); font-size:12px; margin-top:34px; border-top:1px solid var(--line);
padding-top:12px; }}
</style></head><body class="dark"><div class="wrap">

<div class="top">
  <h1>College Week {WEEK}</h1>
  <button class="toggle" onclick="document.body.classList.toggle('dark')">Light / dark</button>
</div>
<div class="sub">{SEASON_TXT} &middot; {len(in_scope) + len(final_rows)} games &middot;
{len(in_scope)} still to play, {len(final_rows)} final, {len(cross_rows)} cross-division
&middot; built by the <b>{esc(MODE)}</b> run at {PHX.strftime('%a %-d %b, %-I:%M %p')} Phoenix</div>

<div class="nav">
  <a href="#attn">Needs attention{'' if not ISSUES else f' ({len(ISSUES)})'}</a>
  <a href="#summary">Summary</a>
  <a href="#notes">Game notes</a>
  <a href="#sheet">Cheat sheet</a>
  <a href="#ledger">Ledger</a>
  <a href="#help">How to read</a>
</div>

<div class="banner">
<b>Two readings on every market, because they answer different questions.</b>
<b>Conf</b> is how likely the call is to happen, after the backtest corrected what the model
claims. <b>Value</b> is how far that sits above the break-even the price demands. The
<b>grade</b> is the two weighted together, {100*PICKS.W_CONF:.0f}% confidence and
{100*PICKS.W_VALUE:.0f}% value.
<br><br>
Predicting the winner works and is measured: the outright fit clears zero over
{HEAD.get('model_gap_games', 0):,} games, so moneyline confidence means something. Beating
the number does not. Our rating disagreeing with the market went
{HEAD.get('model_gap_pct', 0):.1f}% and got worse as the disagreement grew, which is why
spread and total confidence sits near a coin flip however big the gap looks. A heavy favorite
can be highly likely and still a poor price, and that is exactly what the two columns are for.
</div>

<h2 id="attn">Needs attention</h2>
{issues_html()}

<h2 id="summary">Summary &mdash; all markets</h2>
{summary_table()}

<h2 id="strategies">Where each strategy stands</h2>
{strategy_table()}

<h2 id="notes">Game notes</h2>
{"".join(game_card(r) for r in in_scope) or '<p class="muted">No in-scope games left to play this week.</p>'}
{('<h3>Already played this week</h3>' + "".join(game_card(r) for r in final_rows)) if final_rows else ''}
{('<h3>Cross-division, for reference</h3>' + "".join(game_card(r) for r in cross_rows)) if cross_rows else ''}

<h2 id="sheet">Team cheat sheet</h2>
<p class="muted">Rating is points against an average FBS team on a neutral field. Talent
prior is where recruiting alone would put a team, form is what results have said on top.</p>
<div class="scroll">{cheat_sheet()}</div>

<h2 id="ledger">Ledger &mdash; week {WEEK}</h2>
{picks_ledger()}
<h3>How our number compares with the market's</h3>
{accuracy_ledger()}

<h2 id="help">How to read</h2>
{how_to_read()}

<footer>
Ratings: opponent-adjusted ridge on game margins, shrunk toward a talent prior.
Home field {HFA:+.1f}. FBS over FCS {META.get('fcs_gap', 0):+.1f}. Built from
{META.get('games_used', 0):,} games across {META.get('teams', 0)} teams.
Picks are append-only and keep the number they were issued at.
No bet sizing or staking advice appears here by design.
</footer>

</div></body></html>"""

bad = []
_body = re.sub(r"<style>.*?</style>|<script>.*?</script>", "", HTML, flags=re.S)
_left = re.findall(r"\{[A-Za-z_][A-Za-z0-9_.\[\]'\"()]*\}", _body)
if _left:
    bad.append(f"unrendered placeholders in the page: {_left[:4]}")
if re.search(r"\bnan\b", _body, re.I):
    bad.append("the page contains the word nan, so a missing number leaked through")
if HTML.count("<html") != 1 or HTML.count("</html>") != 1:
    bad.append("the page markup is not one complete document")
if bad:
    for b in bad:
        print(f"REFUSING TO PUBLISH: {b}")
    sys.exit(1)

with open(os.path.join(DOCS, "index.html"), "w") as f:
    f.write(HTML)
open(os.path.join(DOCS, ".nojekyll"), "w").close()
print(f"\nwrote docs/index.html  ({len(HTML):,} bytes)  week {WEEK}, mode {MODE}")
print(f"wrote docs/picks.csv   ({len(pk)} picks)")
print(f"wrote docs/ledger.csv  ({len(ledger)} rows)")
