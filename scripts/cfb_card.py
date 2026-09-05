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
import ast, html, json, math, os, re, sys
from datetime import datetime, timezone, timedelta
import numpy as np, pandas as pd
from sklearn.linear_model import Ridge
from scipy.stats import norm
import warnings; warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cfb_picks as PICKS

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
DOCS = os.path.abspath(os.path.join(BASE, "..", "docs"))
P = lambda f: os.path.join(DATA, f)
os.makedirs(DOCS, exist_ok=True)

MODE = os.environ.get("CFB_MODE", "rebuild").strip().lower()
NOW = datetime.now(timezone.utc)
PHX = NOW - timedelta(hours=7)

GAME_SD = 15.6
TOTAL_ALPHA = 4.0
TOTAL_CAP = 70
SPPLUS_FLAG = 10.0
PRICE_FLAG = 2.5
PRICE_MAX = 14.0
ML_SANE = 5000


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
season = int(CUR.season.max()) if "season" in CUR.columns else 0
existing = {(r.season, r.week, r.away, r.home, r.market, r.strategy, r.book)
            for r in pk.itertuples()}
issued = 0
PICKS_BY_GAME = {}
for r in rows:
    ps = [] if r["cross"] else PICKS.picks_for(r, r["price"], WEEK)
    PICKS_BY_GAME[(r["away"], r["home"])] = ps
    for p in ps:
        if p["tier"] in ("PASS", "AVOID"):
            continue                      # only PLAY and LEAN become tracked picks
        key = (season, WEEK, r["away"], r["home"], p["market"], p["strategy"], p["book"])
        if key in existing:
            continue
        pk.loc[len(pk)] = [season, WEEK, r["away"], r["home"], p["market"], p["strategy"],
                           p["tier"], p["grade"], p["side"], p["number"], p["book"],
                           NOW.isoformat(), None, None]
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


def decision_table():
    body = []
    for r in rows:
        if r["cross"] or r["final"]:
            continue
        ps = PICKS_BY_GAME.get((r["away"], r["home"]), [])
        tier, grade, _ = PICKS.headline(ps)
        best = ps[0] if ps else None
        if best and best["tier"] in ("PLAY", "LEAN"):
            txt = (f'{esc(best["side"])} {best["number"]:+.1f} '
                   f'<span class="bk">{esc(best["book"])}</span>')
        elif best and best["tier"] == "AVOID":
            txt = ('<span class="muted">no bet. the only angles here backtested '
                   'as losers</span>')
        else:
            txt = '<span class="muted">no pick</span>'
        body.append(f'<tr><td>{esc(r["away"])} at {esc(r["home"])}</td>'
                    f'<td><span class="tier {TC.get(tier,"pass")}">{tier}</span></td>'
                    f'<td class="gr">{grade}</td><td>{txt}</td></tr>')
    if not body:
        return '<p class="muted">No in-scope games left to play this week.</p>'
    return ('<table class="sheet"><thead><tr><th>game</th><th>call</th><th>grade</th>'
            '<th>the pick</th></tr></thead><tbody>' + "".join(body) + "</tbody></table>")


def strategy_table():
    out = []
    for s in PICKS.RECORD:
        tier, grade, pct, (lo, hi), n = PICKS.tier_of(s)
        live = pk[(pk.strategy == s) & pk.result.isin(["win", "loss", "push"])] if len(pk) else pk
        lwin = int((live.result == "win").sum()) if len(live) else 0
        lloss = int((live.result == "loss").sum()) if len(live) else 0
        out.append(f'<tr><td>{esc(s.replace("_", " "))}</td>'
                   f'<td><span class="tier {TC.get(tier,"pass")}">{tier}</span></td>'
                   f'<td class="gr">{grade}</td><td>{pct:.1f}%</td>'
                   f'<td>{lo:.1f} to {hi:.1f}</td><td>{n:,}</td><td>{lwin}-{lloss}</td></tr>')
    return ('<table class="sheet"><thead><tr><th>strategy</th><th>call</th><th>grade</th>'
            '<th>backtest</th><th>95% interval</th><th>games</th><th>live 2026</th>'
            '</tr></thead><tbody>' + "".join(out) + "</tbody></table>")


def picks_ledger():
    if not len(pk):
        return ('<p class="muted">No picks issued yet. Only PLAY and LEAN calls are '
                'recorded, so a week with neither adds no rows.</p>')
    d = pk.sort_values(["week"], ascending=False)
    body = "".join(
        f'<tr><td>{int(x.week)}</td><td>{esc(x.away)} at {esc(x.home)}</td>'
        f'<td>{esc(x.market)}</td><td>{esc(x.side)} {float(x.number):+.1f}</td>'
        f'<td>{esc(x.book)}</td><td class="gr">{esc(x.grade)}</td>'
        f'<td class="{esc(x.result) if isinstance(x.result, str) else ""}">'
        f'{esc(x.result) if isinstance(x.result, str) else "pending"}</td></tr>'
        for x in d.itertuples())
    return (f'<p>{pw} wins, {pl} losses, {pp} pushes on settled picks.</p>'
            '<table class="sheet"><thead><tr><th>wk</th><th>game</th><th>market</th>'
            '<th>pick</th><th>book</th><th>grade</th><th>result</th></tr></thead>'
            '<tbody>' + body + "</tbody></table>")


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

    ps = PICKS_BY_GAME.get((r["away"], r["home"]), [])
    tier, grade, _ = PICKS.headline(ps)
    tag = ('<span class="tag out">out of scope</span>' if r["cross"] else
           f'<span class="tier {TC.get(tier,"pass")}">{tier} {grade}</span>')
    if r["low_info"]:
        tag += '<span class="tag warn">low information</span>'
    callbox = ""
    if ps:
        callbox = '<div class="calls">' + "".join(
            f'<div class="call {TC.get(p["tier"],"pass")}">'
            f'<b>{p["tier"]} {p["grade"]}</b> &middot; {esc(p["market"])} &middot; '
            f'{esc(p["side"])} {p["number"]:+.1f} at {esc(p["book"])}'
            f'<div class="why">{esc(p["reason"])}</div>'
            f'<div class="ev">{esc(p["evidence"])}</div></div>' for p in ps) + "</div>"
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


def issues_html():
    if not ISSUES:
        return '<p class="ok">Nothing to flag.</p>'
    return "".join(f'<div class="issue"><b>{esc(k)}</b> {esc(v)}</div>' for k, v in ISSUES)


in_scope = [r for r in rows if not r["cross"] and not r["final"]]
cross_rows = [r for r in rows if r["cross"] and not r["final"]]
final_rows = [r for r in rows if r["final"]]
tiers = [PICKS.headline(PICKS_BY_GAME.get((r["away"], r["home"]), []))[0] for r in in_scope]
n_play = tiers.count("PLAY")
n_lean = tiers.count("LEAN")

HTML = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>College card &middot; week {WEEK}</title>
<style>
:root {{ color-scheme: dark; --bg:#0d1117; --card:#161b22; --line:#30363d; --tx:#e6edf3;
        --mut:#8b949e; --acc:#58a6ff; --warn:#d29922; --good:#3fb950; --bad:#f85149; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--tx); font:15px/1.5 -apple-system,
        BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif; }}
.wrap {{ max-width:940px; margin:0 auto; padding:16px; }}
h1 {{ font-size:20px; margin:0 0 2px; }}
h2 {{ font-size:15px; color:var(--mut); margin:22px 0 10px; }}
.sub {{ color:var(--mut); font-size:13px; margin-bottom:14px; }}
.banner {{ background:#1c2128; border:1px solid var(--line); border-left:3px solid var(--warn);
        border-radius:6px; padding:12px 14px; margin-bottom:16px; font-size:14px; }}
.banner b {{ color:var(--warn); }}
nav {{ display:flex; gap:6px; margin-bottom:14px; flex-wrap:wrap; }}
nav button {{ background:var(--card); color:var(--tx); border:1px solid var(--line);
        border-radius:6px; padding:8px 14px; font-size:14px; cursor:pointer; }}
nav button[aria-selected=true] {{ background:var(--acc); color:#0d1117; border-color:var(--acc);
        font-weight:600; }}
section[hidden] {{ display:none; }}
.game {{ background:var(--card); border:1px solid var(--line); border-radius:8px;
        padding:12px 14px; margin-bottom:12px; }}
.game.cross {{ opacity:.72; }} .game.final {{ opacity:.85; }}
.game header {{ display:flex; flex-wrap:wrap; align-items:baseline; gap:8px; margin-bottom:8px; }}
.game h3 {{ font-size:16px; margin:0; }}
.kick {{ color:var(--mut); font-size:12px; }}
.tag, .tier {{ font-size:11px; padding:2px 7px; border-radius:99px; border:1px solid var(--line); }}
.tag.out, .tag.done {{ color:var(--mut); }}
.tag.warn {{ color:var(--warn); border-color:var(--warn); }}
.tier.play {{ color:#0d1117; background:var(--good); border-color:var(--good); font-weight:700; }}
.tier.lean {{ color:var(--good); border-color:var(--good); }}
.tier.pass {{ color:var(--mut); }}
.tier.avoid {{ color:var(--bad); border-color:var(--bad); }}
.gr {{ font-weight:700; }}
.bk {{ color:var(--mut); font-size:12px; }}
table.nums {{ width:100%; border-collapse:collapse; font-size:14px; }}
table.nums th {{ text-align:left; color:var(--mut); font-weight:500; font-size:12px; padding:3px 6px; }}
table.nums td {{ padding:4px 6px; border-top:1px solid var(--line); }}
table.nums td:first-child {{ color:var(--mut); width:34%; }}
.calls {{ margin-top:9px; }}
.call {{ border:1px solid var(--line); border-left:3px solid var(--mut); border-radius:6px;
        padding:8px 10px; margin:6px 0; background:#0d1117; font-size:13px; }}
.call.play, .call.lean {{ border-left-color:var(--good); }}
.call.avoid {{ border-left-color:var(--bad); }}
.why {{ margin-top:3px; }}
.ev {{ margin-top:3px; color:var(--mut); font-size:12px; }}
.gap {{ margin-top:9px; font-size:13px; background:#0d1117; border:1px solid var(--line);
        border-radius:6px; padding:8px 10px; }}
.gap.muted {{ color:var(--mut); }}
.price-box, .rs {{ margin-top:9px; border:1px solid var(--line); border-radius:6px;
        padding:8px 10px; background:#0d1117; }}
.ph {{ font-size:11px; text-transform:uppercase; letter-spacing:.5px; color:var(--mut);
        margin-bottom:4px; }}
.pn, .nn {{ font-size:13px; margin:3px 0; }}
.nn span {{ color:var(--mut); }}
.score {{ font-size:15px; font-weight:600; margin:2px 0 4px; }}
table.sheet {{ width:100%; border-collapse:collapse; font-size:13px; }}
table.sheet th {{ text-align:left; color:var(--mut); font-weight:500; padding:6px 8px;
        border-bottom:1px solid var(--line); position:sticky; top:0; background:var(--bg); }}
table.sheet td {{ padding:5px 8px; border-bottom:1px solid var(--line); }}
td.model, td.win {{ color:var(--good); }}
td.market, td.loss {{ color:var(--bad); }}
.scroll {{ overflow-x:auto; }}
.issue {{ background:var(--card); border:1px solid var(--line); border-left:3px solid var(--warn);
        border-radius:6px; padding:9px 12px; margin-bottom:8px; font-size:14px; }}
.ok {{ color:var(--good); }} .muted {{ color:var(--mut); }}
footer {{ color:var(--mut); font-size:12px; margin-top:24px; border-top:1px solid var(--line);
        padding-top:12px; }}
</style></head><body><div class="wrap">

<h1>College card &middot; week {WEEK}</h1>
<div class="sub">{len(in_scope)} still to play, {len(final_rows)} final, {len(cross_rows)}
cross-division. {n_play} PLAY, {n_lean} LEAN. Built by the <b>{esc(MODE)}</b> run at
{PHX.strftime('%a %-d %b, %-I:%M %p')} Phoenix.</div>

<div class="banner">
<b>Grades come from the backtest, not from the size of a number.</b> A call is only PLAY
when a strategy's whole 95% interval sits above the {PICKS.BREAK_EVEN}% break-even. Right
now nothing does. One strategy is a LEAN and two are AVOID, meaning they backtested as
losers. Our rating disagreeing with the market is not by itself a reason to bet: that went
50.3% over 2,789 games and got worse as the disagreement grew.
</div>

<nav>
  <button aria-selected="true" onclick="tab(this,'picks')">Picks</button>
  <button aria-selected="false" onclick="tab(this,'slate')">Slate</button>
  <button aria-selected="false" onclick="tab(this,'sheet')">Cheat sheet</button>
  <button aria-selected="false" onclick="tab(this,'ledger')">Ledger</button>
  <button aria-selected="false" onclick="tab(this,'attn')">Attention{'' if not ISSUES else f' ({len(ISSUES)})'}</button>
</nav>

<section id="picks">
<h2>This week</h2>
{decision_table()}
<h2>Where each strategy stands</h2>
{strategy_table()}
<h2>Every pick issued</h2>
{picks_ledger()}
</section>

<section id="slate" hidden>
{"".join(game_card(r) for r in in_scope) or '<p class="muted">No in-scope games this week.</p>'}
{('<h2>Cross-division, for reference</h2>' + "".join(game_card(r) for r in cross_rows)) if cross_rows else ''}
{('<h2>Already played this week</h2>' + "".join(game_card(r) for r in final_rows)) if final_rows else ''}
</section>

<section id="sheet" hidden>
<p class="muted">Rating is points against an average FBS team on a neutral field. Talent
prior is where recruiting alone would put a team, form is what results have said on top.</p>
<div class="scroll">{cheat_sheet()}</div>
</section>

<section id="ledger" hidden>
<h2>How our number compares with the market's</h2>
{accuracy_ledger()}
</section>

<section id="attn" hidden>{issues_html()}</section>

<footer>
Ratings: opponent-adjusted ridge on game margins, shrunk toward a talent prior.
Home field {HFA:+.1f}. FBS over FCS {META.get('fcs_gap', 0):+.1f}. Built from
{META.get('games_used', 0):,} games across {META.get('teams', 0)} teams.
Picks are append-only and keep the number they were issued at.
No bet sizing or staking advice appears here by design.
</footer>

</div><script>
function tab(btn, id) {{
  document.querySelectorAll('nav button').forEach(function(b) {{
    b.setAttribute('aria-selected', b === btn ? 'true' : 'false');
  }});
  ['picks','slate','sheet','ledger','attn'].forEach(function(s) {{
    document.getElementById(s).hidden = (s !== id);
  }});
}}
</script></body></html>"""

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
