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
import ast, colorsys, html, json, math, os, re, sys, unicodedata, zlib
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
PRICE_PICK = float(MS.TH["price_pick"])
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

TEAMS = load_optional("teams.csv")
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


# ------------------------------------------------------------ team colors
# Ported from the NFL card, machinery and thresholds unchanged. Two problems it
# solves that a raw hex cannot: a navy is unreadable on the dark panel and a gold
# is unreadable on the light one, and a team's primary is sometimes one of those.
# So each theme picks independently -- primary first, because it is the team's
# identity, secondary only if the primary cannot be made readable -- and then
# walks the lightness until it clears a real contrast ratio against that panel.
def _rgb(h):
    h = str(h).strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        raise ValueError(h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _lum(rgb):
    """WCAG relative luminance."""
    def ch(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r_, g_, b_ = (ch(v) for v in rgb)
    return 0.2126 * r_ + 0.7152 * g_ + 0.0722 * b_


def _vivid(hexc, L, sat=0.90):
    """Set lightness and push saturation, keeping hue. Greys stay grey."""
    r_, g_, b_ = (v / 255 for v in _rgb(hexc))
    h_, _l0, s0 = colorsys.rgb_to_hls(r_, g_, b_)
    s_ = s0 if s0 < 0.12 else max(s0, sat)
    r2, g2, b2 = colorsys.hls_to_rgb(h_, L, s_)
    return "#%02X%02X%02X" % (int(r2 * 255), int(g2 * 255), int(b2 * 255))


# Thresholds are contrast ratios against the actual panel color, not raw
# luminance: red is inherently low-luminance and a flat floor rejects it unfairly.
_BG_DARK, _BG_LIGHT = 0.014, 0.97
_MIN_DARK = 4.2 * (_BG_DARK + 0.05) - 0.05
_MAX_LIGHT = (_BG_LIGHT + 0.05) / 4.2 - 0.05


def _pick(primary, secondary, L, min_lum=None, max_lum=None):
    cands = [c for c in (primary, secondary) if c]
    for c in cands:
        try:
            v = _vivid(c, L)
        except ValueError:
            continue
        if min_lum is not None and _lum(_rgb(v)) < min_lum:
            continue
        if max_lum is not None and _lum(_rgb(v)) > max_lum:
            continue
        return v
    # neither cleared the bar: walk the primary's lightness until it does
    try:
        best, LL = _vivid(cands[0], L), L
    except (ValueError, IndexError):
        return None
    if min_lum is not None:
        while _lum(_rgb(best)) < min_lum and LL < 0.90:
            LL += 0.02
            best = _vivid(cands[0], LL)
    if max_lum is not None:
        while _lum(_rgb(best)) > max_lum and LL > 0.14:
            LL -= 0.02
            best = _vivid(cands[0], LL)
    return best


def team_slug(name):
    """A CSS-safe class suffix. Team names carry spaces, accents and brackets."""
    n = unicodedata.normalize("NFKD", str(name))
    n = "".join(c for c in n if not unicodedata.combining(c))
    n = re.sub(r"[^A-Za-z0-9]+", "-", n).strip("-").lower()
    return n or "team"


def build_team_colors():
    """slug -> (light, dark). Empty when teams.csv is missing, which is fine:
    the class is simply never emitted and names render in the ordinary color."""
    if TEAMS is None or "school" not in TEAMS.columns:
        return {}
    pri_col = next((c for c in ("color",) if c in TEAMS.columns), None)
    alt_col = next((c for c in ("alternateColor", "alt_color", "alternate_color")
                    if c in TEAMS.columns), None)
    if pri_col is None:
        return {}
    out = {}
    for t in TEAMS.itertuples(index=False):
        school = str(getattr(t, "school", "") or "").strip()
        if not school:
            continue
        pri = getattr(t, pri_col, None)
        alt = getattr(t, alt_col, None) if alt_col else None
        pri = None if pri is None or str(pri).strip().lower() in ("", "nan") else str(pri)
        alt = None if alt is None or str(alt).strip().lower() in ("", "nan") else str(alt)
        if not pri:
            continue
        lig = _pick(pri, alt, 0.36, max_lum=_MAX_LIGHT)
        drk = _pick(pri, alt, 0.63, min_lum=_MIN_DARK)
        if lig and drk:
            out[team_slug(school)] = (lig, drk)
    return out


TEAMCOLOR = build_team_colors()
print(f"team colors: {len(TEAMCOLOR)} teams")


def tm(name):
    """A team name painted in its own color, when we have one."""
    slug = team_slug(name)
    if slug in TEAMCOLOR:
        return f'<span class="tm-{slug}">{esc(name)}</span>'
    return esc(name)


def team_css():
    return ("".join(f".tm-{k}{{color:{v[0]}}}" for k, v in TEAMCOLOR.items())
            + "".join(f"body.dark .tm-{k}{{color:{v[1]}}}" for k, v in TEAMCOLOR.items()))


def _ranks(series, ascending):
    """team -> rank, 1 is best. Used for the offence and defence columns."""
    try:
        return series.rank(ascending=ascending, method="min").astype(int).to_dict()
    except Exception:
        return {}


def team_records():
    """Win-loss from completed games this season. The NFL card has REC; college
    had nothing, so the game cards could not say who was any good so far."""
    rec = {}
    cur = CUR.dropna(subset=["home_points", "away_points"])
    for g in cur.itertuples():
        h, a = str(g.home_team), str(g.away_team)
        hp, ap = float(g.home_points), float(g.away_points)
        for t in (h, a):
            rec.setdefault(t, [0, 0])
        if hp > ap:
            rec[h][0] += 1; rec[a][1] += 1
        elif ap > hp:
            rec[a][0] += 1; rec[h][1] += 1
    return {t: f"{w}-{l}" for t, (w, l) in rec.items()}


REC = team_records()

OFF, DEF, HBUMP, MU = fit_totals()
print(f"totals model: league mean {MU:.1f} per team, home bump {HBUMP:+.2f}")
# Higher offence rating is better; lower defence rating (points allowed) is better.
# Rank over the rated teams only. OFF and DEF are fitted across every team that
# has played, prior seasons included, so ranking them unrestricted printed "#387"
# beside a power rank drawn from 256 -- two different denominators, side by side.
_RATED = [t for t in R.index if t in OFF.index]
OFF_RANK = _ranks(OFF.loc[_RATED], ascending=False)
DEF_RANK = _ranks(DEF.loc[_RATED], ascending=True)
RANK = ({} if "rank" not in R.columns
        else {t: int(v) for t, v in R["rank"].dropna().items()})

# "Unusually low returning production" is stored as a percentile rather than a
# fixed percentage, so it keeps meaning what it says as the file changes from
# season to season instead of going stale. .get keeps a broken state file from
# costing the card, which is the whole point of the fallback.
RET_LOW_PCT = float(MS.TH.get("ret_low_pct", 20.0))
RET_LOW = 0.0
if "ret_percentPPA" in R.columns:
    _rp = pd.to_numeric(R["ret_percentPPA"], errors="coerce").dropna()
    if len(_rp) >= 20:
        RET_LOW = float(np.percentile(_rp, RET_LOW_PCT))
print(f"returning production: bottom {RET_LOW_PCT:.0f}% sits below {RET_LOW:.0%}")


def _sv(team, col):
    """One column as a string, or empty."""
    if team not in R.index or col not in R.columns:
        return ""
    v = R.loc[team].get(col)
    return "" if v is None or (isinstance(v, float) and v != v) else str(v)


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

def dedupe_books(books):
    """One row per book, whatever the feed calls it.

    CFBD returns DraftKings under two spellings, "DraftKings" and "Draft Kings",
    and they are not the same row: the spaced one carries a spread and a total
    but never a moneyline or an opener. Left alone, a game quoted by both gets
    two DraftKings spreads into a median that Bovada only gets one vote in, so
    the consensus quietly leans toward whichever book the feed happens to spell
    twice. Measured on this season's file: 100 games are quoted under both
    spellings and the consensus spread moves on 40 of them once deduplicated,
    by up to 1.25 points. Nothing failed; the market number was just wrong.

    Keep the richest row per normalised name -- the one carrying the most fields
    -- so the moneyline and the opener survive.
    """
    best = {}
    for b in books:
        key = "".join(ch for ch in str(b.get("provider", "")).lower() if ch.isalnum())
        # Underscore keys are ours, not the feed's. Counting them would make a
        # row look richer than it is and let it win the tie-break on nothing.
        score = sum(1 for k, v in b.items() if v is not None and not k.startswith("_"))
        if key not in best or score > best[key][0]:
            best[key] = (score, b)
    return [b for _s, b in best.values()]


def _f(v):
    """A number, or nothing. Blank cells and stray text must not become 0.0."""
    try:
        f = float(v)
        return f if np.isfinite(f) else None
    except (TypeError, ValueError):
        return None


# --------------------------------------------- the second odds feed
# CFBD's line feed is the weakest thing it gives us. The DraftKings
# double-spelling above came from there, and this week 33 of its quotes
# carried -100000 placeholders that had to be thrown away. The Odds API
# supplies the same games from nine books, so the consensus stops resting
# on one thin source.
#
# The two feeds do not agree on a single team name. Measured on the first
# real response: 88 distinct names came back and NOT ONE matched CFBD
# exactly. The Odds API says "Memphis Tigers"; CFBD says "Memphis". A plain
# join would have matched nothing. A fuzzy join would have matched the wrong
# games and said nothing, which is worse. So names are resolved explicitly,
# every match has to survive three checks, and anything that fails is dropped
# and counted rather than guessed at.
ODDS_ALIAS = {
    # The Odds API writes a plain i, CFBD uses the okina. No prefix rule can
    # bridge that, so it is stated. This and Southeastern Louisiana were the
    # only two of 88 names the prefix rule could not place, and Southeastern
    # Louisiana is FCS, which the card does not price anyway.
    "hawaii rainbow warriors": "Hawai'i",
}
# This map lives here rather than in model_state.json on purpose. It is a fact
# about how an outside feed spells things, not a constant the model is tuned
# on, and model_state.py carries a fallback copy of everything in that file, so
# putting it there would mean the same table written twice. See 4.3h.

ODDS_TIME_TOL_H = 12.0   # kickoff agreement required, in hours


def build_odds_resolver(cfbd_names):
    """One Odds API team name -> one CFBD team name, or nothing.

    Longest match first, so "Miami (OH) RedHawks" cannot be captured by the
    shorter "Miami". A name that matches nothing returns None and its game is
    dropped; it is never approximated.
    """
    by_len = sorted({str(c) for c in cfbd_names if isinstance(c, str)},
                    key=len, reverse=True)
    cache = {}

    def resolve(name):
        n = str(name).strip()
        if n in cache:
            return cache[n]
        out = ODDS_ALIAS.get(n.lower())
        if out is None:
            for c in by_len:
                if n == c or n.startswith(c + " "):
                    out = c
                    break
        cache[n] = out
        return out
    return resolve


def load_odds_feed(schedule):
    """Odds API rows, keyed by the CFBD (away, home) pair.

    Four checks, and a row has to pass all four:
      1. the quote was taken BEFORE kickoff,
      2. both team names resolve to a CFBD name,
      3. that pair is exactly one scheduled game,
      4. the book's kickoff agrees with the schedule's to within
         ODDS_TIME_TOL_H hours.

    Check 1 is not a formality, it is the one that matters most. This endpoint
    keeps quoting a game after it has started, and an in-play price is not a
    line, it is a scoreboard. Measured on the first real merge: Louisiana Tech
    was quoted at -83.5 with a total of 93.5, and Mississippi State at -49.5.
    Folded into the consensus those moved the market number on 27 of 51 games
    and made three totals physically impossible. That is section 4.3e in a new
    costume: a number that is only meaningful before kickoff leaking in after.
    A row counts only if the book's own last_update predates kickoff, so the
    test travels with the row and does not depend on when this card runs.

    Check 4 is what stops a wrong name resolution from landing quietly on a
    real game: two teams can be misread, but they will not also be playing at
    the same hour.
    """
    stats = dict(rows=0, quotes=0, games=0, books=0,
                 unresolved_name=0, no_game=0, wrong_time=0, in_play=0, names=[])
    path = P("odds_api.csv")
    if not os.path.exists(path):
        return {}, stats
    try:
        O = pd.read_csv(path)
    except Exception as e:
        print(f"  odds_api.csv could not be read ({e}); carrying on without it")
        return {}, stats
    if O.empty:
        return {}, stats
    stats["rows"] = int(len(O))

    sched = {}
    for _, g in schedule.iterrows():
        k = (str(g.away_team), str(g.home_team))
        sched.setdefault(k, []).append(g.start_date)

    resolve = build_odds_resolver(
        set(schedule.home_team.dropna()) | set(schedule.away_team.dropna()))
    O["_kick"] = pd.to_datetime(O.get("commence_time"), errors="coerce", utc=True)
    # When the book last moved this price. Fall back to when we pulled it.
    O["_quoted"] = pd.to_datetime(O.get("last_update"), errors="coerce", utc=True)
    O["_quoted"] = O["_quoted"].fillna(
        pd.to_datetime(O.get("fetched_utc"), errors="coerce", utc=True))

    out, bad_names = {}, set()
    for _, r in O.iterrows():
        # In-play first, before anything else is spent on the row.
        if pd.isna(r["_kick"]) or pd.isna(r["_quoted"]) or r["_quoted"] >= r["_kick"]:
            stats["in_play"] += 1
            continue
        h, a = resolve(r.get("home_team")), resolve(r.get("away_team"))
        if h is None or a is None:
            stats["unresolved_name"] += 1
            if h is None:
                bad_names.add(str(r.get("home_team")))
            if a is None:
                bad_names.add(str(r.get("away_team")))
            continue
        kicks = sched.get((a, h))
        if not kicks or len(kicks) != 1:
            stats["no_game"] += 1
            continue
        k0, k1 = kicks[0], r["_kick"]
        if pd.isna(k0) or pd.isna(k1) or \
                abs((k1 - k0).total_seconds()) > ODDS_TIME_TOL_H * 3600:
            stats["wrong_time"] += 1
            continue
        out.setdefault((a, h), []).append({
            "provider": str(r.get("book") or "book"),
            "spread": _f(r.get("spread")),
            "spreadOpen": None,          # this feed quotes now, not the opener
            "overUnder": _f(r.get("total")),
            "overUnderOpen": None,
            "homeMoneyline": _f(r.get("home_moneyline")),
            "awayMoneyline": _f(r.get("away_moneyline")),
            "_src": "oddsapi",
        })
        stats["quotes"] += 1
    stats["games"] = len(out)
    stats["books"] = len({b["provider"] for v in out.values() for b in v})
    stats["names"] = sorted(bad_names)
    return out, stats


ODDS_BOOKS, ODDS_STATS = load_odds_feed(CUR)
if ODDS_STATS["rows"]:
    print(f"odds api: {ODDS_STATS['quotes']:,} quotes from "
          f"{ODDS_STATS['books']} books on {ODDS_STATS['games']} games "
          f"(dropped {ODDS_STATS['in_play']} in-play, "
          f"{ODDS_STATS['unresolved_name']} unknown name, "
          f"{ODDS_STATS['no_game']} no scheduled game, "
          f"{ODDS_STATS['wrong_time']} kickoff disagreed)")




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
    books = dedupe_books(list(lr["_books"] if lr is not None else [])
                         + ODDS_BOOKS.get((away, home), []))

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
# ---- this season's settled picks, fed back into the tiers ----
# A strategy belongs to one market. picks.csv carries three generations of
# moneyline rows -- some blank, some tagged model_gap_early from before the
# moneyline strategies existed, some correct -- and pooling a moneyline result
# into the spread strategy's record would quietly corrupt the tier that gates
# every grade. So a row only counts when its recorded strategy matches its
# market, and the ones that do not are reported rather than dropped in silence.
STRAT_MARKET = {"model_gap_early": "spread", "model_gap_late": "spread",
                "price_gap": "spread", "total_model": "total", "total_over": "total",
                "moneyline_fav": "moneyline", "moneyline_dog": "moneyline"}


def live_results():
    live, mismatched, unattributed = {}, 0, 0
    if not len(pk):
        return live, mismatched, unattributed
    for r in pk.itertuples():
        res = str(getattr(r, "result", "") or "").strip().lower()
        if res not in ("win", "loss", "push"):
            continue
        strat = _k(getattr(r, "strategy", ""))
        market = _k(getattr(r, "market", ""))
        if not strat:
            unattributed += 1
            continue
        want = STRAT_MARKET.get(strat)
        if want is None or (want != market and not (want == "spread" and market == "price")):
            mismatched += 1
            continue
        d = live.setdefault(strat, {"w": 0, "l": 0, "p": 0, "rets": []})
        d["w" if res == "win" else "l" if res == "loss" else "p"] += 1
        if strat in ("moneyline_fav", "moneyline_dog"):
            # a moneyline tier is measured in return, so the price is the unit
            try:
                price = float(getattr(r, "number"))
            except (TypeError, ValueError):
                continue
            dec = 1.0 + (price / 100.0 if price > 0 else 100.0 / -price)
            d["rets"].append(0.0 if res == "push" else (dec - 1.0 if res == "win" else -1.0))
    return live, mismatched, unattributed


LIVE, LIVE_MISMATCHED, LIVE_UNATTRIBUTED = live_results()
PICKS.set_live(LIVE)
if LIVE:
    print("  live results folded into the tiers: "
          + ", ".join(f"{k} {v['w']}-{v['l']}" for k, v in sorted(LIVE.items())))
if LIVE_MISMATCHED or LIVE_UNATTRIBUTED:
    print(f"  not counted: {LIVE_MISMATCHED} recorded against the wrong market, "
          f"{LIVE_UNATTRIBUTED} with no strategy")

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
    mkt = med([b.get("spread") for b in
               dedupe_books(list(lr["_books"] if lr is not None else [])
                            + ODDS_BOOKS.get((away, home), []))])
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
    if ODDS_STATS["rows"] and ODDS_STATS["unresolved_name"]:
        nm = ", ".join(ODDS_STATS["names"][:6])
        more = "" if len(ODDS_STATS["names"]) <= 6 else f" and {len(ODDS_STATS['names']) - 6} more"
        out.append(("odds names",
                    f"{ODDS_STATS['unresolved_name']} odds quotes name a team this card "
                    f"cannot place: {nm}{more}. They were dropped rather than matched to "
                    f"the nearest name."))
    if ODDS_STATS["rows"] and (ODDS_STATS["no_game"] or ODDS_STATS["wrong_time"]):
        out.append(("odds unmatched",
                    f"{ODDS_STATS['no_game']} odds quotes had no single scheduled game and "
                    f"{ODDS_STATS['wrong_time']} disagreed with the schedule on kickoff by "
                    f"more than {ODDS_TIME_TOL_H:.0f} hours. Both were dropped."))
    if ODDS_STATS["in_play"]:
        out.append(("odds in play",
                    f"{ODDS_STATS['in_play']} odds quotes were taken after kickoff. An "
                    f"in-play price is a scoreboard, not a line, so they were dropped "
                    f"before the consensus was taken."))
    if not ODDS_STATS["rows"]:
        out.append(("no second odds feed",
                    "odds_api.csv is missing or empty, so the consensus rests on CFBD's "
                    "line feed alone. The card still builds; it just has fewer books."))
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
    if LIVE_MISMATCHED or LIVE_UNATTRIBUTED:
        out.append(("picks unattributed",
                    f"{LIVE_MISMATCHED} settled picks are recorded against a strategy that "
                    f"does not match their market and {LIVE_UNATTRIBUTED} carry no strategy "
                    f"at all, so they are left out of the live tier numbers."))
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

# Does the answer depend on where the backtest window starts? cfb_backtest.py
# re-runs the headline dropping the earliest seasons one at a time and writes
# what it found. A verdict that is the same on every window means the start
# year is doing no work. One that changes means the window is doing some of
# the work, and the card has to say so rather than quote the pooled figure as
# though the choice were free. Empty until the backtest has been re-run.
SENS = BT.get("sensitivity") or {}
SENS_SUM = BT.get("sensitivity_summary") or {}
SENS_VERDICTS = SENS_SUM.get("verdicts") or sorted({str(v.get("verdict", "")) for v in SENS.values()})
SENS_STABLE = bool(SENS_SUM.get("stable")) if SENS_SUM else len(SENS_VERDICTS) == 1


def sens_html():
    if not SENS:
        return ("<p class=\"muted\">The window check has not been run yet. Re-run the "
                "cfb-backtest workflow and it appears here.</p>")
    rows = []
    for start, v in sorted(SENS.items()):
        iv = v.get("interval") or [0, 0]
        rows.append(
            "<tr><td>" + esc(str(start)) + " on</td><td>" + f"{int(v.get('n', 0)):,}"
            + "</td><td>" + f"{int(v.get('w', 0))}-{int(v.get('l', 0))}"
            + "</td><td>" + f"{float(v.get('pct', 0)):.1f}%"
            + "</td><td>" + f"{float(iv[0]):.1f} to {float(iv[1]):.1f}"
            + "</td><td>" + esc(str(v.get("verdict", ""))) + "</td></tr>")
    head = ("<table class=\"sheet\"><thead><tr><th>window</th><th>games</th><th>record</th>"
            "<th>win rate</th><th>95% interval</th><th>verdict</th></tr></thead><tbody>")
    drift = SENS_SUM.get("drifted") or []
    fi = SENS_SUM.get("full_interval") or [0, 0]
    span = f"{float(fi[0]):.1f}% to {float(fi[1]):.1f}%"
    if SENS_STABLE:
        tail = ("<p>Every window says the same thing (" + esc(SENS_VERDICTS[0])
                + "), so the start year is not doing the work and the pooled figure "
                  "above stands on its own.</p>")
    elif not drift:
        tail = ("<p>The label changes (" + esc(", ".join(SENS_VERDICTS))
                + ") but every window's win rate still sits inside the full window's "
                + esc(span) + ". A shorter window has fewer games and a wider interval, and a "
                  "wider interval stops excluding break-even on its own. That is a shrinking "
                  "sample, not a changing sport, and the pooled figure stands.</p>")
    else:
        tail = ("<p><b>The label changes (" + esc(", ".join(SENS_VERDICTS))
                + ") and the win rate moves with it.</b> The windows starting "
                + esc(", ".join(str(x) for x in drift)) + " sit outside the full window's "
                + esc(span) + ", so this is not just a wider interval on fewer games. The start "
                  "year is doing some of the work and the pooled figure is not safe to quote on "
                  "its own. Read it the other way too: the recent seasons look better than the "
                  "pooled record, and they are also the thinnest samples here. Neither reading "
                  "is established, which is the honest answer until more seasons land.</p>")
    return head + "".join(rows) + "</tbody></table>" + tail


SENS_HTML = sens_html()


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


def phx_parts(iso):
    """Kickoff split the way the NFL card's first three columns want it.

    Returns (date, day, time) in Phoenix time: "09/05", "Sat", "09:00".
    """
    if not iso:
        return ("", "", "")
    try:
        t = datetime.fromisoformat(iso) - timedelta(hours=7)
    except Exception:
        return ("", "", "")
    return (t.strftime("%m/%d"), t.strftime("%a"), t.strftime("%H:%M"))


def spread_label(r):
    if r["model"] is None:
        return "&mdash;"
    m = r["model"]
    fav, n2 = (r["home"], -m) if m > 0 else (r["away"], m)
    return f"{esc(fav)} {n2:+.1f}"


TC = {"PLAY": "play", "LEAN": "lean", "PASS": "pass", "AVOID": "avoid"}
# Which conferences are FBS. Used only to split the cheat sheet into two blocks,
# never inside the fit -- see do not reintroduce (a) and (b).
FBS_CONF = {"ACC", "American Athletic", "Big 12", "Big Ten", "Conference USA",
            "FBS Independents", "Mid-American", "Mountain West", "Pac-12", "SEC",
            "Sun Belt"}
TG = {"A": "t-a", "B": "t-b", "C": "t-c", "D": "t-d"}
PK = {"A": "pk-a", "B": "pk-b", "C": "pk-c", "D": "pk-d"}


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
    """The NFL card's summary table, column for column.

    Date, day and time, game, then each market as both sides with the called
    side picked out, its grade beside it, and one plain-English column at the
    end. Seventeen columns had grown up here, four of them per market, and it
    was no longer obvious which grade belonged to which bet. The two college
    readings that the NFL card has no equivalent for -- confidence, and value
    over the price -- ride under the grade rather than in columns of their own.
    """
    body, days, gids = [], [], []
    for r in rows:
        if r["cross"] or r["final"]:
            continue
        mk, pp = PICKS_BY_GAME.get((r["away"], r["home"]), ({}, []))
        sp, ml, tt = mk.get("spread"), mk.get("moneyline"), mk.get("total")
        date, day, time = phx_parts(r["kick"])
        gid = f'{r["away"]}@{r["home"]}'
        if day and day not in days:
            days.append(day)
        gids.append((gid, r["away"], r["home"]))

        def tip(v):
            if not v:
                return ""
            bits = [f"confidence {v.get('conf_pct', 0):.1f}% against a break-even of "
                    f"{v.get('break_even', 0):.1f}%, so {v.get('margin_pp', 0):+.1f} points "
                    f"of value",
                    f"confidence grade {v.get('conf', 'D')}, value grade {v.get('value', 'D')}, "
                    f"merged {PICKS.W_CONF:.0%} confidence / {PICKS.W_VALUE:.0%} value"]
            if v.get("tier"):
                bits.append(f"strategy {v.get('strategy') or 'none'}, backtested {v['tier']}")
            if v.get("capped"):
                bits.append("capped: " + str(v["capped"]))
            if v.get("calibration"):
                bits.append(str(v["calibration"]))
            return esc(". ".join(bits) + ".")

        def gcell(v):
            """One grade pill, with confidence and value on the line beneath it."""
            if not v or v.get("number") is None:
                return '<td><span class="tag t-n">&mdash;</span></td>'
            g = v.get("grade", "D")
            star = '<span class="cap">*</span>' if v.get("capped") else ""
            return (f'<td title="{tip(v)}"><span class="tag {TG.get(g, "t-n")}">{g}{star}</span>'
                    f'<span class="pct">{v.get("conf_pct", 0):.0f}% &middot; '
                    f'{v.get("margin_pp", 0):+.1f}</span></td>')

        def side_cell(home_txt, away_txt, home_is_pick, v):
            """Both sides of the market, the called one picked out in its grade colour."""
            if not v or v.get("number") is None:
                return '<td class="grp num">&mdash;</td>'
            pc = PK.get(v.get("grade", "D"), "pk-d")
            h = (f'<span class="{pc}">{esc(home_txt)}</span>' if home_is_pick
                 else f'<span class="num">{esc(home_txt)}</span>')
            a = (f'<span class="{pc}">{esc(away_txt)}</span>' if not home_is_pick
                 else f'<span class="num">{esc(away_txt)}</span>')
            return f'<td class="grp">{h} <span class="num">/</span> {a}</td>'

        if sp and r["mkt"] is not None:
            sp_td = side_cell(f'{r["home"]} {-r["mkt"]:+.1f}', f'{r["away"]} {r["mkt"]:+.1f}',
                              sp["side"] == r["home"], sp)
        else:
            sp_td = '<td class="grp num">&mdash;</td>'

        if ml and r["home_ml"] is not None and r["away_ml"] is not None:
            ml_td = side_cell(f'{r["home"]} {int(r["home_ml"]):+d}',
                              f'{r["away"]} {int(r["away_ml"]):+d}',
                              ml["side"] == r["home"], ml)
        else:
            ml_td = '<td class="grp num">&mdash;</td>'

        tot_td = (f'<td class="num grp">{r["mkt_total"]:.1f}</td>'
                  if r["mkt_total"] is not None else '<td class="num grp">&mdash;</td>')
        if tt and tt.get("number") is not None:
            pick_td = (f'<td><span class="{PK.get(tt.get("grade", "D"), "pk-d")}">'
                       f'{esc(str(tt["side"]).upper())}</span></td>')
        else:
            pick_td = '<td class="num">&mdash;</td>'

        reads = what_this_tells_you(r, mk, pp)
        read_td = (f'<td class="grp rd">{esc(reads)}</td>' if reads != "nothing unusual"
                   else '<td class="grp rd"><span class="none">nothing unusual</span></td>')

        body.append(
            f'<tr class="row" data-day="{esc(day)}" data-gid="{esc(gid)}">'
            f'<td class="num">{esc(date)}</td>'
            f'<td class="num">{esc(day)} {esc(time)}</td>'
            f'<td class="game">{tm(r["away"])} <span class="num">@</span> '
            f'{tm(r["home"])}</td>'
            + sp_td + gcell(sp) + ml_td + gcell(ml) + tot_td + pick_td + gcell(tt)
            + read_td + '</tr>')

    if not body:
        return '<p class="muted">No in-scope games left to play this week.</p>'

    flt = ['<div class="filters"><div class="fg"><b>Day</b>']
    for d in days:
        flt.append(f'<label><input type="checkbox" class="fd" value="{esc(d)}" '
                   f'checked onchange="flt()">{esc(d)}</label>')
    flt.append('</div><div class="fg"><b>Game</b>')
    for gid, a, h in gids:
        flt.append(f'<label><input type="checkbox" class="fgm" value="{esc(gid)}" '
                   f'checked onchange="flt()">{esc(a)} @ {esc(h)}</label>')
    flt.append('</div><div class="fg"><b>&nbsp;</b><button onclick="allOn()">Select all</button> '
               '<button onclick="allOff()">Clear</button>'
               '<div id="fcount" class="none" style="margin-top:6px"></div></div></div>')

    return ("".join(flt)
            + '<div class="scroll"><table><thead><tr>'
              '<th>Date</th><th>Day / Time</th><th>Game</th>'
              '<th class="grp">Spread</th><th>Grade</th>'
              '<th class="grp">Moneyline</th><th>Grade</th>'
              '<th class="grp">Total</th><th>Pick</th><th>Grade</th>'
              '<th class="grp">What this tells you</th></tr></thead><tbody>'
            + "".join(body) + '</tbody></table></div>'
            + '<p class="muted">Each market shows both sides, with the one we would take '
              'picked out. The pill is the <b>grade</b>. Under it, the first figure is '
              '<b>confidence</b>, how likely that call is to happen once the backtest has '
              'corrected what the model claims, and the second is <b>value</b>, how many '
              'points of it sit above the break-even the price demands. A star means the '
              'grade was capped by the strategy\'s backtested record. Hover any grade for '
              'the working.</p>')


def strategy_table():
    out = []
    for s in PICKS.RECORD:
        tier, pct, (lo, hi), n = PICKS.tier_of(s)
        # the same filtered numbers the tier was pooled from, not a second count
        # off the raw file -- otherwise the column and the evidence line disagree
        lv = LIVE.get(s) or {}
        lwin, lloss = int(lv.get("w", 0)), int(lv.get("l", 0))
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


def _tv(team, col):
    """One column out of the ratings frame for one team, or None."""
    if team not in R.index or col not in R.columns:
        return None
    return num(R.loc[team].get(col))


def _cmp_row(label, a_val, h_val, a_num=None, h_num=None, lower_better=False):
    """One row of the away-versus-home table, the better side shaded.

    Straight port of the NFL card's _cmp_row, so the two pages read the same.
    """
    ac = hc = ""
    if a_num is not None and h_num is not None and a_num != h_num:
        a_better = (a_num < h_num) if lower_better else (a_num > h_num)
        ac, hc = (" bet", "") if a_better else ("", " bet")
    return (f'<tr><td class="cl">{label}</td><td class="ca{ac}">{a_val}</td>'
            f'<td class="ch{hc}">{h_val}</td></tr>')


def _grp(label):
    return (f'<tr class="grp2"><td class="cl">{label}</td>'
            f'<td class="ca">&nbsp;</td><td class="ch">&nbsp;</td></tr>')


def compare_table(r):
    """The NFL card's unit-by-unit comparison, in the terms college actually has.

    No play-by-play efficiency exists here, so where the NFL shows pass and rush
    ranks this shows what the college model is built from: the rating and its two
    halves, the points model's offence and defence, SP+ as the independent
    cross-check, and returning production.
    """
    a, h = r["away"], r["home"]

    def fmt1(v, plus=True):
        return "&mdash;" if v is None else (f"{v:+.1f}" if plus else f"{v:.1f}")

    def rk(d, t):
        return f'#{d[t]}' if t in d else "&mdash;"

    def pts(series, t):
        return "&mdash;" if t not in series.index else f"{float(series[t]) + MU:.1f}"

    rows = [
        _cmp_row("Record", esc(REC.get(a, "0-0")), esc(REC.get(h, "0-0"))),
        _cmp_row("Conference", esc(str(_sv(a, "conference") or "&mdash;")),
                 esc(str(_sv(h, "conference") or "&mdash;"))),
        _cmp_row("Power rank", rk(RANK, a), rk(RANK, h),
                 _tv(a, "rank"), _tv(h, "rank"), True),
        _cmp_row("Rating", fmt1(_tv(a, "rating")), fmt1(_tv(h, "rating")),
                 _tv(a, "rating"), _tv(h, "rating")),
        _cmp_row("Talent prior", fmt1(_tv(a, "talent_prior")), fmt1(_tv(h, "talent_prior")),
                 _tv(a, "talent_prior"), _tv(h, "talent_prior")),
        _cmp_row("Form on top of it", fmt1(_tv(a, "form")), fmt1(_tv(h, "form")),
                 _tv(a, "form"), _tv(h, "form")),
        _cmp_row("Returning production",
                 ("&mdash;" if _tv(a, "ret_percentPPA") is None
                  else f'{_tv(a, "ret_percentPPA"):.0%}'),
                 ("&mdash;" if _tv(h, "ret_percentPPA") is None
                  else f'{_tv(h, "ret_percentPPA"):.0%}'),
                 _tv(a, "ret_percentPPA"), _tv(h, "ret_percentPPA")),
        _grp("OFFENSE"),
        _cmp_row("Points model rank", rk(OFF_RANK, a), rk(OFF_RANK, h),
                 OFF_RANK.get(a), OFF_RANK.get(h), True),
        _cmp_row("Points expected", pts(OFF, a), pts(OFF, h),
                 (None if a not in OFF.index else float(OFF[a])),
                 (None if h not in OFF.index else float(OFF[h]))),
        _cmp_row("SP+ offense", fmt1(_tv(a, "sp_offense.rating")),
                 fmt1(_tv(h, "sp_offense.rating")),
                 _tv(a, "sp_offense.rating"), _tv(h, "sp_offense.rating")),
        _grp("DEFENSE"),
        _cmp_row("Points model rank", rk(DEF_RANK, a), rk(DEF_RANK, h),
                 DEF_RANK.get(a), DEF_RANK.get(h), True),
        _cmp_row("Points allowed", pts(DEF, a), pts(DEF, h),
                 (None if a not in DEF.index else float(DEF[a])),
                 (None if h not in DEF.index else float(DEF[h])), True),
        # Lower is better in SP+ defense: it correlates -0.83 with team rating in
        # this file, Ohio State 8.4 against Massachusetts 41.2. Shaded the other
        # way it marked the worse defence as the better one on every card.
        _cmp_row("SP+ defense", fmt1(_tv(a, "sp_defense.rating")),
                 fmt1(_tv(h, "sp_defense.rating")),
                 _tv(a, "sp_defense.rating"), _tv(h, "sp_defense.rating"), True),
    ]
    return (f'<table class="cmp"><thead><tr><th></th>'
            f'<th class="ca">{tm(a)}</th><th class="ch">{tm(h)}</th>'
            f'</tr></thead><tbody>' + "".join(rows) + '</tbody></table>')


def numbers_table(r):
    """Our number against the market's, market by market."""
    def row(label, ours, theirs, gap=None):
        g = "&mdash;" if gap is None else f"{gap:+.1f}"
        return (f'<tr><td class="cl">{label}</td><td class="ca">{ours}</td>'
                f'<td class="ch">{theirs}</td><td class="ch">{g}</td></tr>')
    sp_ours = "&mdash;" if r["model"] is None else f'{esc(r["home"])} {-r["model"]:+.1f}'
    sp_mkt = "&mdash;" if r["mkt"] is None else f'{esc(r["home"])} {-r["mkt"]:+.1f}'
    tot_ours = "&mdash;" if r["model_total"] is None else f'{r["model_total"]:.1f}'
    tot_mkt = "&mdash;" if r["mkt_total"] is None else f'{r["mkt_total"]:.1f}'
    tot_gap = (None if (r["model_total"] is None or r["mkt_total"] is None)
               else r["model_total"] - r["mkt_total"])
    ml = "&mdash;"
    if r["home_ml"] is not None and r["away_ml"] is not None:
        ml = (f'{esc(r["home"])} {int(r["home_ml"]):+d} / '
              f'{esc(r["away"])} {int(r["away_ml"]):+d}')
    mktp = ("&mdash;" if r["home_ml_prob"] is None
            else f'{esc(r["home"])} {100 * r["home_ml_prob"]:.0f}% to win, vig removed')
    out = ['<table class="cmp"><thead><tr><th></th><th class="ca">Our number</th>'
           '<th class="ch">The market</th><th class="ch">Gap</th></tr></thead><tbody>',
           row("Spread", sp_ours, sp_mkt, r["gap"]),
           row("Total", tot_ours, tot_mkt, tot_gap),
           f'<tr><td class="cl">Moneyline</td><td class="ca" colspan="3">{ml}</td></tr>',
           f'<tr><td class="cl">Market win probability</td>'
           f'<td class="ca" colspan="3">{mktp}</td></tr>']
    if r["sp_margin"] is not None:
        out.append(f'<tr><td class="cl">SP+ cross-check</td><td class="ca" colspan="3">'
                   f'{esc(r["home"])} {-r["sp_margin"]:+.1f}'
                   f'{" &mdash; diverges from our number" if r["low_info"] else ""}'
                   f'</td></tr>')
    out.append('</tbody></table>')
    return "".join(out)


def call_block(r, mk, pp):
    """Every graded market on this game, with the two readings behind the grade."""
    entries = [(name, v, "consensus") for name, v in mk.items()]
    entries += [("price consistency", p, p.get("book", "")) for p in pp]
    if not entries:
        return ('<div class="lbl">The call</div>'
                '<ul class="nl"><li><span class="none">No graded market on this game.</span>'
                '</li></ul>')
    rows = []
    for name, v, book in entries:
        star = '<span class="cap">*</span>' if v.get("capped") else ""
        g = v.get("grade", "D")
        bits = []
        if v.get("strategy"):
            # The evidence line already opens with the tier, so only name the
            # strategy here or the card reads "backtested AVOID. AVOID."
            bits.append("strategy " + esc(str(v["strategy"]).replace("_", " ")))
        if v.get("capped"):
            bits.append("capped: " + esc(str(v["capped"])))
        if v.get("evidence"):
            bits.append(esc(str(v["evidence"])))
        rows.append(
            f'<tr><td class="cl">{esc(name)}</td>'
            f'<td class="ca"><b>{esc(str(v.get("side", "")))} '
            f'{fmtnum(name if name in ("spread", "moneyline", "total") else "spread", v.get("number"))}</b>'
            + (f' <span class="bk">{esc(book)}</span>' if book and book != "consensus" else '')
            + f'</td>'
            f'<td class="ch"><span class="tag {TG.get(g, "t-n")}">{g}{star}</span></td>'
            f'<td class="ch">{v.get("conf_pct", 0):.0f}%</td>'
            f'<td class="ch">{v.get("margin_pp", 0):+.1f}</td>'
            f'<td class="cl wrap">{". ".join(bits)}</td></tr>')
    return ('<div class="lbl">The call</div>'
            '<table class="cmp calls"><thead><tr><th>Market</th><th class="ca">Side</th>'
            '<th class="ch">Grade</th><th class="ch">Conf</th><th class="ch">Value</th>'
            '<th>Why that grade</th></tr></thead><tbody>'
            + "".join(rows) + '</tbody></table>')


def game_meta(r):
    """The one-line header under the matchup, the way the NFL card writes it."""
    bits = []
    d, day, t = phx_parts(r["kick"])
    if day:
        bits.append(f"{day} {d} &middot; {t}")
    if r["venue"]:
        place = str(r["venue"])
        if isinstance(r["city"], str):
            place += f", {r['city']}"
            if isinstance(r["state"], str):
                place += f" {r['state']}"
        bits.append(esc(place))
    if str(r["dome"]).lower() == "true":
        bits.append("indoors")
    if str(r["grass"]).lower() == "true":
        bits.append("grass")
    elif str(r["grass"]).lower() == "false":
        bits.append("turf")
    el = num(r["elevation"])
    if el is not None and el > 3000:
        bits.append(f"{el:.0f} ft elevation")
    if r["neutral"]:
        bits.append("neutral site")
    ca, ch = _sv(r["away"], "conference"), _sv(r["home"], "conference")
    if ca and ch and ca == ch:
        bits.append("conference game")
    elif r["cross"]:
        bits.append("cross-division")
    tw, wd = num(r["temp"]), num(r["wind"])
    if tw is not None:
        w = f"{tw:.0f}&deg;F"
        if wd is not None:
            w += f", {wd:.0f} mph wind" + (" &mdash; wind flag" if wd >= 15 else "")
        bits.append(w)
    if r["rest_home"] is not None and r["rest_away"] is not None:
        diff = int(r["rest_home"]) - int(r["rest_away"])
        if diff:
            side = r["home"] if diff > 0 else r["away"]
            bits.append(f"rest {abs(diff)} days to {esc(side)}")
    return " &middot; ".join(bits)


def preview_rows(r):
    """The two at-a-glance lines the NFL card puts in the collapsed header."""
    def line(t):
        rt = _tv(t, "rating")
        return (f'<span class="pvT">{tm(t)}</span>'
                f'<span class="pvS">{esc(REC.get(t, "0-0"))}</span>'
                f'<span class="pvU"><b>RTG</b> '
                f'{"&mdash;" if rt is None else f"{rt:+.1f}"}</span>'
                f'<span class="pvU"><b>OFF</b> '
                f'{f"#{OFF_RANK[t]}" if t in OFF_RANK else "&mdash;"}</span>'
                f'<span class="pvU"><b>DEF</b> '
                f'{f"#{DEF_RANK[t]}" if t in DEF_RANK else "&mdash;"}</span>')
    return (f'<div class="pvRow">{line(r["away"])}</div>'
            f'<div class="pvRow">{line(r["home"])}</div>')


def game_flags(r, mk, pp):
    """The chips down the right of the collapsed header."""
    f = []
    if pp:
        f.append("price gap")
    sp, ml = mk.get("spread"), mk.get("moneyline")
    if sp and ml and sp["side"] != ml["side"]:
        f.append("markets split")
    if r["low_info"]:
        f.append("models disagree")
    if r["cross"]:
        f.append("no pick")
    for t in (r["away"], r["home"]):
        rp = _tv(t, "ret_percentPPA")
        if rp is not None and rp < RET_LOW:
            f.append("thin returning")
            break
    if r["books"] and r["books"] <= 2:
        f.append("thin market")
    return ('<div class="gcF">'
            + "".join(f'<span class="gcX">{x}</span>' for x in f) + '</div>')


def sec(title, items):
    if not items:
        return ""
    return (f'<div class="lbl">{title}</div><ul class="nl">'
            + "".join(f"<li>{i}</li>" for i in items) + "</ul>")


def notes_sections(r):
    """Whatever notes.json holds for this game, in the NFL card's order."""
    n = r["notes"] or {}
    if not isinstance(n, dict):
        return ""
    def lst(key):
        v = n.get(key)
        if not v:
            return []
        return [esc(str(x)) for x in (v if isinstance(v, list) else [v])]
    out = [sec("Injury report", lst("injuries")),
           sec("Returning from injury", lst("returning")),
           sec("Transfers &amp; roster moves", lst("trades") + lst("transfers")),
           sec("Coaching &amp; suspensions", lst("coaching") + lst("suspensions")),
           sec("Line movement", lst("movement")),
           sec("Notable", lst("birthdays") + lst("notable"))]
    ex = n.get("experts")
    if ex:
        items = []
        for e in (ex if isinstance(ex, list) else [ex]):
            if isinstance(e, dict):
                items.append(f'<b>{esc(str(e.get("name", "")))}</b> '
                             f'({esc(str(e.get("record", "record n/a")))}) &mdash; '
                             f'{esc(str(e.get("pick", "")))}')
            else:
                items.append(esc(str(e)))
        out.append(sec("Expert picks", items))
    known = {"injuries", "returning", "trades", "transfers", "coaching", "suspensions",
             "movement", "birthdays", "notable", "experts"}
    extra = [f'<i>{esc(k)}</i> &mdash; {esc(", ".join(map(str, v)) if isinstance(v, list) else str(v))}'
             for k, v in n.items() if k not in known and v]
    out.append(sec("Also in the notes file", extra))
    return "".join(out)


def conditions_section(r):
    bits = []
    tw, wd, pr = num(r["temp"]), num(r["wind"]), num(r["precip"])
    if tw is not None:
        w = f"{tw:.0f}&deg;F"
        if wd is not None:
            w += f", wind {wd:.0f} mph"
        if pr is not None:
            w += f", {pr:.0f}% chance of rain"
        bits.append("Forecast at kickoff: " + w
                    + (". Wind is not adjusted for in the totals model, because there is no "
                       "historical college weather on hand to measure it against."
                       if (wd is not None and wd >= 15) else "."))
    rest = [f"{esc(t)} {int(r[k])} days"
            for t, k in ((r["home"], "rest_home"), (r["away"], "rest_away"))
            if r[k] is not None]
    if rest:
        bits.append("Rest: " + ", ".join(rest) + ".")
    tv = num(r["travel"])
    if tv:
        bits.append(f"{esc(r['away'])} travels {tv:.0f} miles.")
    move = []
    if r["open_mkt"] is not None and r["mkt"] is not None:
        d = r["mkt"] - r["open_mkt"]
        move.append(f"Spread opened {-r['open_mkt']:+.1f}, now {-r['mkt']:+.1f}"
                    + (f", {abs(d):.1f} toward {esc(r['home'] if d > 0 else r['away'])}."
                       if abs(d) >= 0.5 else ", unmoved."))
    if r["open_total"] is not None and r["mkt_total"] is not None:
        dt = r["mkt_total"] - r["open_total"]
        move.append(f"Total opened {r['open_total']:.1f}, now {r['mkt_total']:.1f}"
                    + (f", {dt:+.1f}." if abs(dt) >= 0.5 else ", unmoved."))
    if r["books"]:
        move.append(f"{r['books']} book{'' if r['books'] == 1 else 's'} quoted.")
    return sec("Conditions and market", bits + move)


def explainers(r, mk, pp):
    """The paragraphs the NFL card writes when something is odd about a game."""
    out = []
    if r["low_info"] and r["sp_margin"] is not None and r["model"] is not None:
        lean = r["home"] if r["sp_margin"] > r["model"] else r["away"]
        out.append(sec("Models disagree", [
            f'Our rating makes this {r["model"]:+.1f} from the home side. <b>SP+</b>, which is '
            f'built independently and kept out of our fit precisely so it can act as a check, '
            f'makes it {r["sp_margin"]:+.1f} &mdash; {abs(r["model"] - r["sp_margin"]):.1f} '
            f'points apart, with SP+ higher on <b>{esc(lean)}</b>. Anything past '
            f'{SPPLUS_FLAG:.0f} points is flagged. One of the two is badly wrong here and there '
            f'is no way to know which, so treat this as a low-information game.']))
    thin = []
    for t, side in ((r["away"], "away"), (r["home"], "home")):
        rp = _tv(t, "ret_percentPPA")
        if rp is not None and rp < RET_LOW:
            thin.append(f'<b>{esc(t)}</b> ({side}) returns {rp:.0%} of last season\'s production, '
                        f'below the {RET_LOW:.0%} mark.')
    if thin:
        out.append(sec("Roster turnover, the known blind spot", thin + [
            'The ratings do not read returning production: they carry last season\'s form '
            'forward whatever left the building. This is the leading known defect in the model '
            'and it bites hardest in week 1. Where our number sits well under the market on a '
            'team like this, read it as that artifact until something else explains it.']))
    # The graded price picks carry the pick's own fields; the raw notes behind them
    # carry the two prices. Read the disagreement off the notes, not off the pick.
    if r["price"]:
        p = max(r["price"], key=lambda x: abs(x.get("diff", 0)))
        lines = [
            f'<b>{esc(str(p.get("book", "the book")))}</b> posts {p["spread"]:+.1f} on the spread '
            f'while its own moneyline implies {p["equiv"]:+.1f} &mdash; a '
            f'{abs(p.get("diff", 0)):.1f} point disagreement between the same book\'s two prices, '
            f'so one of them is stale.']
        if pp:
            lines.append('This is arithmetic on the price rather than a view on the game, which '
                         'is why it survives the backtest result intact. It does not change which '
                         'side to take and it does not affect the total.')
        else:
            lines.append(f'It is under the {PRICE_PICK:.1f} point mark that makes it a pick, so it '
                         f'is shown for information only.')
        if len(r["price"]) > 1:
            lines.append("Other books: " + "; ".join(
                f'{esc(str(q.get("book", "")))} {q["spread"]:+.1f} against {q["equiv"]:+.1f}'
                for q in r["price"] if q is not p) + ".")
        out.append(sec("Which ticket to buy", lines))
    sp, ml = mk.get("spread"), mk.get("moneyline")
    if sp and ml and sp["side"] != ml["side"]:
        out.append(sec("Markets point different ways", [
            f'Best cover is <b>{esc(sp["side"])}</b> at {100 * sp["p"]:.1f}% to cover. Best value '
            f'to win outright is <b>{esc(ml["side"])}</b>, which we make {100 * ml["p"]:.1f}% '
            f'against a price implying {100 * (ml["p"] - ml["edge"] / 100):.1f}%. Those are not '
            f'the same question, and disagreeing is not in itself a reason to bet either one.']))
    if r["cross"]:
        out.append(sec("Why there is no pick here", [
            'One side is FBS and the other FCS. A single offset cannot undo per-team inflation '
            'inside a division whose schedule barely touches FBS, so cross-division games are '
            'shown for reference and never given a pick.']))
    return "".join(out)


def game_card(r):
    """One collapsible game, laid out the way the NFL card lays one out."""
    mk, pp = PICKS_BY_GAME.get((r["away"], r["home"]), ({}, []))
    _d, day, _t = phx_parts(r["kick"])
    gid = f'{r["away"]}@{r["home"]}'
    best = PICKS.best_of(mk, pp)
    head_tag = ""
    if r["final"]:
        head_tag = '<span class="gcX">final</span>'
    elif best:
        head_tag = f'<span class="tag {TG.get(best[0], "t-n")}">{best[0]}</span>'

    body = []
    if r["final"]:
        hp, ap = r["final"]
        actual = hp - ap
        line = [f'<b>{esc(r["home"])} {hp}, {esc(r["away"])} {ap}</b> &mdash; '
                f'final margin {actual:+d}.']
        if r["model"] is not None and r["mkt"] is not None:
            me, ke = abs(r["model"] - actual), abs(r["mkt"] - actual)
            who = ("Our number was closer" if me < ke else
                   "The market was closer" if ke < me else "Both missed by the same")
            line.append(f'We said {r["model"]:+.1f}, the market said {r["mkt"]:+.1f}. '
                        f'{who}, by {abs(me - ke):.1f}.')
        body.append(sec("Result", [" ".join(line)]))
        mine = pk[(pk.away == r["away"]) & (pk.home == r["home"])] if len(pk) else pk
        if len(mine):
            body.append(sec("How our picks graded", [
                f'{esc(str(x.market))}: {esc(str(x.side))} {esc(str(x.number))} at '
                f'{esc(str(x.book))} &mdash; <b>'
                f'{esc(x.result) if isinstance(x.result, str) else "pending"}</b>'
                for x in mine.itertuples()]))
    else:
        body.append(call_block(r, mk, pp))

    body.append('<div class="lbl">Side by side</div>' + compare_table(r))
    body.append('<div class="lbl">Our number against the market</div>' + numbers_table(r))
    body.append(conditions_section(r))
    body.append(explainers(r, mk, pp))
    body.append(notes_sections(r))

    return (f'<details class="gc" data-day="{esc(day)}" data-gid="{esc(gid)}"><summary>'
            f'<span class="car">&rsaquo;</span>'
            f'<span><span class="gcH">{tm(r["away"])}'
            f'<span class="vs">at</span>{tm(r["home"])}</span>'
            f'<div class="gcM">{game_meta(r)}</div>'
            f'<div class="gcP">{preview_rows(r)}</div></span>'
            + (f'<div class="gcF">{head_tag}</div>' if r["final"]
               else game_flags(r, mk, pp))
            + '</summary><div class="body">'
            + "".join(body) + '</div></details>')


def _rank_table(d, start_at_one=False):
    """One ranked block, in the NFL card's column style."""
    body = []
    for i, t in enumerate(d.itertuples(index=False), 1):
        n = i if start_at_one else int(getattr(t, "rank", i))
        def num(attr, fmt="{:+.1f}"):
            v = getattr(t, attr, None)
            return "&mdash;" if v is None or (isinstance(v, float) and v != v) else fmt.format(v)
        body.append(
            f'<tr><td class="num">{n}</td>'
            f'<td class="game">{tm(t.team)}</td>'
            f'<td class="num">{esc(getattr(t, "conference", "") or "")}</td>'
            f'<td class="num">{num("rating")}</td>'
            f'<td class="num">{num("talent_prior")}</td>'
            f'<td class="num">{num("form")}</td>'
            f'<td class="num">{num("sp_rating")}</td>'
            f'<td class="num">{num("ret_percentPPA", "{:.0%}")}</td></tr>')
    return ('<div class="scroll"><table><thead><tr><th>#</th><th>Team</th><th>Conf</th>'
            '<th>Rating</th><th>Talent prior</th><th>Form</th><th>SP+</th>'
            '<th>Ret. prod.</th></tr></thead><tbody>'
            + "".join(body) + '</tbody></table></div>')


def _tier_frame():
    d = R.reset_index()
    if "team" not in d.columns:
        d = d.rename(columns={d.columns[0]: "team"})
    # The ratings file carries a division label. Prefer it: a hardcoded conference
    # list goes stale every time a school moves, and this one is written by the fetch.
    if "division" in d.columns and d["division"].notna().any():
        d["_fbs"] = d["division"].astype(str).str.lower().eq("fbs")
    elif "conference" in d.columns:
        d["_fbs"] = d["conference"].isin(FBS_CONF)
    else:
        d["_fbs"] = True
    return d.sort_values("rating", ascending=False)


def cheat_sheet():
    """Two open blocks, FBS then FCS, the way the NFL card opens AFC and NFC."""
    d = _tier_frame()
    out = []
    for label, sub in (("FBS", d[d._fbs]), ("FCS and other", d[~d._fbs])):
        if not len(sub):
            continue
        out.append(f'<details open><summary>{label} &mdash; ranked 1 to {len(sub)}</summary>'
                   + _rank_table(sub, start_at_one=True) + '</details>')
    return "".join(out) or '<p class="muted">No ratings on file.</p>'


def rankings_by_conference():
    """The NFL card's rankings by division, one collapsed block per conference."""
    d = _tier_frame()
    if "conference" not in d.columns:
        return '<p class="muted">No conference labels on file.</p>'
    out = []
    _fbs_conf = set(d[d._fbs].conference.dropna().unique())
    for cf in sorted({c for c in d.conference.dropna().unique() if str(c).strip()},
                     key=lambda c: (c not in _fbs_conf, str(c))):
        sub = d[d.conference == cf]
        if not len(sub):
            continue
        n = len(sub)
        out.append(f'<details><summary>{esc(str(cf))} &mdash; {n} '
                   f'{"team" if n == 1 else "teams"}</summary>'
                   + _rank_table(sub, start_at_one=True) + '</details>')
    return "".join(out) or '<p class="muted">No conference labels on file.</p>'


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
<tr><td><b>Confidence floor</b></td>
<td>Nothing under {PICKS.CONF_FLOOR:.0f}% likely can grade above D, whatever the price offers.
This floor is <b>{"measured" if PICKS.CONF_FLOOR_MEASURED else "chosen, not measured"}</b>:
{esc(PICKS.CONF_FLOOR_NOTE)}. The backtest buckets moneyline bets by corrected probability and
asks whether each bucket made money; where the bottom buckets lost with their whole 95%
interval below zero, the top of that run is the floor. An 8% shot at +1800 clears its
break-even on paper and used to reach a C on value alone. At that probability the model would
have to be right to a fraction of a point for the value figure to mean anything, and nothing
measures it that finely.</td></tr>
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

<h2>Does the window decide the answer?</h2>
<p>The backtest starts in 2017 because that is the start of the transfer portal era and
betting line coverage thins out before it. That is a judgement, not a measurement, so it is
checked rather than trusted: the same headline is re-run on windows that drop the earliest
seasons one at a time.</p>
{SENS_HTML}
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
    "odds in play": ("INFO", "Some second-feed prices were taken after kickoff",
                     "No action. That endpoint keeps quoting a game once it starts, and an "
                     "in-play price is a scoreboard rather than a line, so it is dropped before "
                     "the consensus is taken."),
    "odds names": ("WARN", "The second odds feed named a team this card cannot place",
                   "Usually an FCS side the card does not price, which is harmless. If it is a "
                   "team that should be here, add the spelling to ODDS_ALIAS in cfb_card.py. "
                   "Nothing is ever matched to a near miss."),
    "odds unmatched": ("INFO", "Some second-feed quotes did not line up with a scheduled game",
                       "No action. A quote has to name one scheduled game and agree with it on "
                       "kickoff, and anything that does not is dropped rather than guessed at."),
    "no second odds feed": ("INFO", "Only CFBD is supplying prices",
                            "The consensus still works, on fewer books. Check that ODDS_API_KEY "
                            "is set and that the last run was inside the freshness window."),
    "picks unattributed": ("WARN", "Some settled picks cannot be credited to a strategy",
                           "Rows written before the moneyline strategies existed. Picks are append-only, so they stay as issued and are simply not counted."),
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
# Which view an issue belongs under. The NFL card tags every issue this way so a
# ledger problem does not shout at you while you are reading the slate. "all"
# means it is about the page itself and shows wherever you are.
ISSUE_VIEW = {
    "missing game": "card", "duplicate": "card", "no line": "card",
    "unrated team": "card", "total out of range": "card", "empty card": "card",
    "placeholder moneylines": "card", "no weather": "card", "no venues": "card",
    "gap looks wrong": "card",
    "odds names": "card", "odds unmatched": "card", "no second odds feed": "card",
    "odds in play": "card",
    "count mismatch": "cheat",
    "duplicate picks": "ledger", "picks cleaned": "ledger",
    "picks unattributed": "ledger",
    "state file": "all", "backtest date": "all",
}


def issues_html():
    if not ISSUES:
        # tagged like a real issue so the view filter hides the heading and this
        # together, instead of leaving a bare "Nothing to flag" under a hidden h2
        return ('<div class="card iss" data-view="all"><b>Nothing to flag.</b> '
                'Every self-check passed.</div>')
    out = []
    for kind, msg in ISSUES:
        lvl, title, fix = FIXES.get(kind, ("WARN", kind.title(), "No fix recorded."))
        out.append(
            f'<div class="card iss lv{LVL[lvl]}" data-view="{ISSUE_VIEW.get(kind, "card")}">'
            f'<div class="lvl"><span class="tag t{LVL[lvl]}">{lvl}</span> {esc(title)}</div>'
            f'<div class="why"><b>Why it matters:</b> {esc(msg)}</div>'
            f'<div class="fix"><b>Fix:</b> {esc(fix)}</div></div>')
    return "".join(out)


# One page per week, the way the NFL card does it. Every run writes an archive
# copy beside index.html, and the dropdown is built from whatever is on disk, so
# it fills in as the season goes rather than needing a list kept by hand.
def week_options():
    weeks = set()
    try:
        for f in os.listdir(DOCS):
            m = re.fullmatch(r"week(\d+)\.html", f)
            if m:
                weeks.add(int(m.group(1)))
    except OSError:
        pass
    weeks.add(int(WEEK))
    out = []
    for w in sorted(weeks):
        cur = (w == int(WEEK))
        # the current week is always index.html, so a bookmark of the root keeps working
        href = "index.html" if cur else f"week{w}.html"
        out.append(f'<option value="{href}"{" selected" if cur else ""}>'
                   f'Week {w}{" (current)" if cur else ""}</option>')
    return "".join(out)


WEEKOPTS = week_options()

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
--sp:#553a7a; --spbg:#efe7f7; --sep:#aab4c0;
--d:#a8324a; --dbg:#fbe9ed; }}
body.dark {{ --ink:#e6eaf0; --mute:#9aa5b3; --line:#2b333d; --bg:#12161c; --pan:#1a1f27;
--hd:#222833; --hov:#20262f; --a:#4ade80; --abg:#12321f; --b:#7cb8f0; --bbg:#0f2740;
--c:#e0c766; --cbg:#332c12; --n:#8b95a1; --nbg:#252b34; --fl:#e0913f; --flbg:#3a2712;
--sp:#c4a8ee; --spbg:#2c2140; --sep:#5a6675;
--d:#f4899f; --dbg:#3d1622; }}
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
.gA {{ color:var(--a); }} .gB {{ color:var(--b); }} .gC {{ color:var(--c); }} .gD {{ color:var(--d); }}
.pct {{ display:block; font-size:10px; font-weight:400; opacity:.75; }}
.cap {{ color:var(--fl); cursor:help; }}
/* The summary table, copied from the NFL card so the two pages read the same.
   A grade is a pill; the side we would take is coloured to match it. */
.game {{ font-weight:600; }}
td.rd {{ white-space:normal; font-size:12px; min-width:230px; line-height:1.4; }}
.t-a {{ background:var(--abg); color:var(--a); }}
.t-b {{ background:var(--bbg); color:var(--b); }}
.t-c {{ background:var(--cbg); color:var(--c); }}
/* D used to share --n with t-n, the "no market" grey, so a graded pick and
   an empty cell looked the same. D is a judgement and gets its own colour;
   the grey now means only that there is nothing there. */
.t-d {{ background:var(--dbg); color:var(--d); }}
.t-n {{ background:var(--nbg); color:var(--n); }}
.pk-a {{ color:var(--a); font-weight:700; }}
.pk-b {{ color:var(--b); font-weight:700; }}
.pk-c {{ color:var(--c); font-weight:700; }}
.pk-d {{ color:var(--d); font-weight:700; }}
.none {{ color:var(--mute); font-size:13px; font-style:italic; }}
.filters {{ background:var(--pan); border:1px solid var(--line); border-radius:8px;
padding:11px 13px; margin-bottom:11px; display:flex; gap:20px; flex-wrap:wrap;
align-items:flex-start; }}
.fg {{ font-size:12.5px; }}
.fg b {{ display:block; font-size:11px; text-transform:uppercase; letter-spacing:.06em;
color:var(--mute); margin-bottom:5px; }}
label {{ display:inline-flex; align-items:center; gap:4px; margin:0 9px 3px 0; cursor:pointer; }}
button {{ font:inherit; font-size:13px; padding:6px 10px; border:1px solid var(--line);
border-radius:6px; background:var(--pan); color:var(--ink); cursor:pointer; }}
.scroll {{ background:var(--pan); }}
.hide {{ display:none; }}
select, button {{ font:inherit; font-size:13px; padding:6px 10px; border:1px solid var(--line);
border-radius:6px; background:var(--pan); color:var(--ink); cursor:pointer; }}
a.btn {{ font-size:13px; padding:6px 11px; border:1px solid var(--line); border-radius:6px;
background:var(--pan); color:var(--ink); text-decoration:none; white-space:nowrap; }}
a.btn:hover {{ border-color:var(--mute); }}
.top {{ margin-bottom:6px; }}
/* The collapsible game cards, ported from the NFL page. */
details.gc {{ background:var(--pan); border:1px solid var(--line); border-radius:10px;
margin-bottom:10px; padding:0; }}
.gc>summary {{ cursor:pointer; padding:14px 16px; list-style:none;
display:grid; grid-template-columns:22px 1fr auto; gap:12px; align-items:start; }}
.gc>summary::-webkit-details-marker {{ display:none; }}
.gc>summary:hover {{ background:var(--hov); border-radius:10px; }}
.gc[open]>summary {{ border-bottom:1px solid var(--line); border-radius:10px 10px 0 0; }}
.gc .car {{ color:var(--mute); font-size:15px; line-height:1.25; transition:transform .15s;
display:inline-block; text-align:center; }}
.gc[open] .car {{ transform:rotate(90deg); }}
.gcH {{ font-size:15.5px; font-weight:600; line-height:1.3; letter-spacing:-.01em; }}
.gcH .vs {{ color:var(--mute); font-weight:400; font-size:13px; margin:0 6px; }}
.gcM {{ font-size:11.5px; color:var(--mute); margin-top:3px;
font-variant-numeric:tabular-nums; }}
.gcP {{ font-size:12.5px; color:var(--mute); margin-top:5px; line-height:1.5; }}
.pvRow {{ display:flex; flex-wrap:wrap; align-items:baseline; margin-top:4px; gap:0; }}
.pvRow>span {{ padding:2px 12px; border-left:2px solid var(--sep); line-height:1.35; }}
.pvRow>span:first-child {{ padding-left:0; border-left:none; }}
.pvT {{ font-weight:700; font-size:13px; min-width:150px; color:var(--ink); }}
.pvS {{ font-variant-numeric:tabular-nums; min-width:42px; }}
.pvU b {{ font-size:10px; letter-spacing:.06em; color:var(--mute); font-weight:700; }}
.gcF {{ display:flex; flex-direction:column; gap:4px; align-items:flex-end; padding-top:2px; }}
.gcX {{ font-size:10.5px; font-weight:600; color:var(--fl); background:var(--flbg);
border-radius:20px; padding:2px 9px; white-space:nowrap; }}
.gc .body {{ padding:14px 16px 16px; }}
.gc .body .lbl:first-child {{ margin-top:0; }}
.lbl {{ font-size:10.5px; text-transform:uppercase; letter-spacing:.06em; color:var(--mute);
font-weight:600; margin-top:16px; margin-bottom:5px; }}
.nl {{ margin:5px 0 0; padding-left:17px; font-size:13.5px; }}
.nl li {{ margin:3px 0; }}
.cmp {{ width:100%; border-collapse:collapse; font-size:12.5px; margin-bottom:4px; }}
.cmp th {{ background:transparent; border-bottom:1px solid var(--line); padding:5px 8px;
font-size:12px; text-transform:none; letter-spacing:0; font-weight:600; }}
.cmp th.ca, .cmp th.ch {{ text-align:center; }}
.cmp td {{ padding:5px 8px; border-bottom:1px solid var(--line); white-space:nowrap; }}
.cmp td.cl {{ color:var(--mute); }}
.cmp td.ca, .cmp td.ch {{ text-align:center; font-variant-numeric:tabular-nums; }}
.cmp tr.grp2 td {{ font-weight:700; background:var(--hd); font-size:10.5px;
letter-spacing:.08em; color:var(--mute); }}
.cmp td.bet {{ background:rgba(13,122,79,.13); font-weight:600; }}
body.dark .cmp td.bet {{ background:rgba(74,222,128,.15); }}
.cmp td.wrap {{ white-space:normal; font-size:12px; line-height:1.4; min-width:220px; }}
.cmp.calls td.ca {{ white-space:nowrap; }}
@media(max-width:640px) {{ .gc>summary {{ grid-template-columns:20px 1fr; }}
.gcF {{ display:none; }} .pvRow>span {{ padding:2px 8px; }} .pvT {{ min-width:110px; }} }}
details {{ background:var(--pan); border:1px solid var(--line); border-radius:8px;
padding:12px 15px; margin-top:10px; }}
details .scroll {{ margin-top:9px; }}
summary {{ cursor:pointer; font-weight:600; font-size:14px; }}
summary:focus {{ outline:none; }}
summary:focus-visible {{ outline:2px solid var(--b); outline-offset:-2px; border-radius:6px; }}
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
{team_css()}
</style></head><body><div class="wrap">

<div class="top">
  <h1>College Week {WEEK}</h1>
  <select id="view" onchange="setView()">
    <option value="card">Weekly Card</option>
    <option value="cheat">Team Cheat Sheet</option>
    <option value="ledger">Ledger &amp; Results</option>
  </select>
  <select id="wk" onchange="goWeek()" title="View another week">{WEEKOPTS}</select>
  <a class="btn" href="https://github.com/fourty2se7en/cfb-card/actions/workflows/cfb-card.yml"
     target="_blank" rel="noopener" title="Opens the run screen on GitHub">Update now &rsaquo;</a>
  <button id="thm" onclick="tog()" style="margin-left:auto">Dark mode</button>
</div>
<div class="sub">{SEASON_TXT} &middot; {len(in_scope) + len(final_rows)} games &middot;
{len(in_scope)} still to play, {len(final_rows)} final, {len(cross_rows)} cross-division
&middot; built by the <b>{esc(MODE)}</b> run at {PHX.strftime('%a %-d %b, %-I:%M %p')} Phoenix</div>

<div class="nav" id="nav"></div>

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

<div id="v-card">
<h2 id="summary">Summary &mdash; all markets</h2>
{summary_table()}

<h2 id="strategies">Where each strategy stands</h2>
{strategy_table()}

<h2 id="notes">Game notes</h2>
<div style="margin:-2px 0 10px"><button onclick="expAll(1)">Expand all</button>
<button onclick="expAll(0)">Collapse all</button></div>
{"".join(game_card(r) for r in in_scope) or '<p class="muted">No in-scope games left to play this week.</p>'}
{('<h3>Already played this week</h3>' + "".join(game_card(r) for r in final_rows)) if final_rows else ''}
{('<h3>Cross-division, for reference</h3>' + "".join(game_card(r) for r in cross_rows)) if cross_rows else ''}

</div><!-- /v-card -->

<div id="v-cheat">
<h2 id="sheet">Team cheat sheet</h2>
<p class="muted">Rating is points against an average FBS team on a neutral field. Talent
prior is where recruiting alone would put a team, form is what results have said on top.
SP+ runs alongside as a cross-check and is kept out of the ratings.</p>
{cheat_sheet()}

<h2 id="conf">Rankings by conference</h2>
<p class="muted">The same ratings, one block per conference. FBS first.</p>
{rankings_by_conference()}

</div><!-- /v-cheat -->

<div id="v-ledger">
<h2 id="ledger">Ledger &mdash; week {WEEK}</h2>
{picks_ledger()}
<h3>How our number compares with the market's</h3>
{accuracy_ledger()}

</div><!-- /v-ledger -->

<h2 id="help">How to read</h2>
{how_to_read()}

<footer>
Ratings: opponent-adjusted ridge on game margins, shrunk toward a talent prior.
Home field {HFA:+.1f}. FBS over FCS {META.get('fcs_gap', 0):+.1f}. Built from
{META.get('games_used', 0):,} games across {META.get('teams', 0)} teams.
Picks are append-only and keep the number they were issued at.
No bet sizing or staking advice appears here by design.
</footer>

</div>
<script>
// Day and game filters over the summary table. An empty group hides everything;
// a fully ticked group imposes no constraint. Same rule as the NFL card.
function flt(){{
 var dAll=document.querySelectorAll('.fd').length, gAll=document.querySelectorAll('.fgm').length;
 var ds=[].slice.call(document.querySelectorAll('.fd:checked')).map(function(e){{return e.value}});
 var gs=[].slice.call(document.querySelectorAll('.fgm:checked')).map(function(e){{return e.value}});
 [].slice.call(document.querySelectorAll('.row')).forEach(function(rw){{
   var ok;
   if(ds.length===0 || gs.length===0) ok=false;
   else ok=(ds.length===dAll || ds.indexOf(rw.dataset.day)>-1)
        && (gs.length===gAll || gs.indexOf(rw.dataset.gid)>-1);
   rw.style.display = ok ? '' : 'none';}});
 var n=0;
 [].slice.call(document.querySelectorAll('.row')).forEach(function(rw){{
   if(rw.style.display!=='none') n++;}});
 var c=document.getElementById('fcount');
 if(c) c.textContent=n+' of '+gAll+' games shown';}}
// ---- the three views, and the nav strip that changes with them ----
var NAVS={{
 card:[['attn','Needs attention'],['summary','Summary'],['strategies','Where each strategy stands'],
       ['notes','Game notes'],['help','How to read']],
 cheat:[['sheet','Team cheat sheet'],['conf','Rankings by conference'],['help','How to read']],
 ledger:[['ledger','Ledger'],['help','How to read']]}};
function mkLink(p){{
 var t=document.getElementById(p[0]); if(!t) return null;
 var a=document.createElement('a'); a.href='#'+p[0]; a.textContent=p[1];
 a.onclick=function(e){{e.preventDefault(); t.scrollIntoView({{behavior:'smooth',block:'start'}});}};
 return a;}}
function setView(){{
 var v=document.getElementById('view').value;
 ['card','cheat','ledger'].forEach(function(k){{
   var el=document.getElementById('v-'+k); if(el) el.classList.toggle('hide', v!==k);}});
 var n=document.getElementById('nav');
 if(n){{n.innerHTML=''; (NAVS[v]||[]).forEach(function(p){{var a=mkLink(p); if(a) n.appendChild(a);}});}}
 // an issue belongs to a view; "all" is about the page itself and always shows
 var any=false;
 [].slice.call(document.querySelectorAll('.iss')).forEach(function(el){{
   var t=el.dataset.view||'card', on=(t==='all'||t===v);
   el.style.display=on?'':'none'; if(on) any=true;}});
 var hdr=document.getElementById('attn');
 if(hdr) hdr.classList.toggle('hide', !any);
 try{{localStorage.setItem('cfbview', v);}}catch(e){{}}
}}
function goWeek(){{var v=document.getElementById('wk').value; if(v) location.href=v;}}
function tog(){{
 var d=document.body.classList.toggle('dark');
 document.getElementById('thm').textContent=d?'Light mode':'Dark mode';
 try{{localStorage.setItem('cfbthm', d?'1':'0');}}catch(e){{}}}}
try{{
 if(localStorage.getItem('cfbthm')!=='0'){{
   document.body.classList.add('dark');
   document.getElementById('thm').textContent='Light mode';}}
 var sv=localStorage.getItem('cfbview');
 if(sv) document.getElementById('view').value=sv;
}}catch(e){{}}
setView();

function allOn(){{[].slice.call(document.querySelectorAll('.fd,.fgm')).forEach(function(e){{e.checked=true}});flt();}}
function allOff(){{[].slice.call(document.querySelectorAll('.fd,.fgm')).forEach(function(e){{e.checked=false}});flt();}}
function expAll(o){{[].slice.call(document.querySelectorAll('details.gc')).forEach(function(d){{d.open=!!o;}});}}
flt();
</script>
</body></html>"""

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
# The archive copy the week dropdown points at. index.html is always the current
# week, so a bookmark of the root keeps working; week{N}.html is what you get
# when you pick an earlier week. Written every run, so the current week's archive
# stays in step with the page until the week rolls over and it freezes.
_archive = os.path.join(DOCS, f"week{int(WEEK)}.html")
with open(_archive, "w") as f:
    f.write(HTML)
open(os.path.join(DOCS, ".nojekyll"), "w").close()
print(f"\nwrote docs/index.html  ({len(HTML):,} bytes)  week {WEEK}, mode {MODE}")
print(f"wrote docs/week{int(WEEK)}.html  (archive copy)")
print(f"wrote docs/picks.csv   ({len(pk)} picks)")
print(f"wrote docs/ledger.csv  ({len(ledger)} rows)")
