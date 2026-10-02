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
import card_chrome as CHROME
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


# Weekly news, researched by hand because it exists in no dataset. Section 3.2
# of the project instructions says this file lives at scripts/notes.json, and
# it did not: the card only ever looked in scripts/data/, which is the folder
# the fetch step owns. A file committed where the instructions said to put it
# was therefore read by nothing, silently, which is why the college card has
# never shown a single note. Both places are checked now, scripts/ first,
# because that is the documented location and it sits outside the data
# pipeline. The card says which one it read so this cannot go quiet again.
NOTES = {}
_NOTES_AT = ""
for _p in (os.path.join(BASE, "notes.json"), P("notes.json")):
    if not os.path.exists(_p):
        continue
    try:
        NOTES = json.load(open(_p))
        _NOTES_AT = os.path.relpath(_p, os.path.dirname(BASE))
        print(f"notes.json: {len(NOTES)} games have notes, read from {_NOTES_AT}")
        break
    except Exception as e:
        print(f"{_p} could not be read ({e}); carrying on without it")
# What changed since the last run. The research file is rewritten by hand each
# week, so a diff against the previous copy is the only way to see what the
# latest run added. Same mechanism and same snapshot file as the NFL card.
# "log" is skipped: it is an object recorded to newslog.csv, never rendered.
CHANGES, PREV_TS = {}, None
_SNAP = P("notes_snapshot.json")
if NOTES:
    _prev = {}
    if os.path.exists(_SNAP):
        try:
            _sn = json.load(open(_SNAP))
            _prev = _sn.get("notes", {})
            PREV_TS = _sn.get("saved")
        except Exception:
            _prev = {}
    if _prev:
        for _g in sorted(set(NOTES) | set(_prev)):
            _now, _was = NOTES.get(_g, {}), _prev.get(_g, {})
            _added, _removed = [], []
            for _sec in (set(_now) | set(_was)) - {"log"}:
                _a = _now.get(_sec, []); _b = _was.get(_sec, [])
                _a = _a if isinstance(_a, list) else [_a]
                _b = _b if isinstance(_b, list) else [_b]
                _as = {json.dumps(x, sort_keys=True) if isinstance(x, dict) else str(x) for x in _a}
                _bs = {json.dumps(x, sort_keys=True) if isinstance(x, dict) else str(x) for x in _b}
                _added += [(_sec, x) for x in sorted(_as - _bs)]
                _removed += [(_sec, x) for x in sorted(_bs - _as)]
            if _added or _removed:
                CHANGES[_g] = {"added": _added, "removed": _removed,
                               "new_game": _g not in _prev, "dropped": _g not in NOTES}
    try:
        json.dump({"saved": datetime.now(timezone.utc).isoformat(timespec="minutes"),
                   "notes": NOTES}, open(_SNAP, "w"), indent=1)
    except Exception as _e:
        print(f"notes snapshot could not be saved ({_e}); next run cannot show what changed")

if not NOTES:
    print("notes.json: not found in scripts/ or scripts/data/, so no game "
          "carries research this week")

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
# A team name no longer sits only on the page background. Now that a pick is a
# tinted chip, the same name can land on any of the grade shades, and a green
# team on the green A shade is exactly the "same colours together" that makes a
# page unreadable. So the bar is set against the WORST background the name can
# ever sit on, not the page.
#
# Light theme: dark text on a light ground, so the darkest chip is the hard
# case. That is --dbg at luminance 0.849. Dark theme: light text on a dark
# ground, so the lightest chip is the hard case, --cbg at 0.026. Both measured
# from the hex values below, not guessed, and both are tighter than the page
# alone would have required.
_BG_LIGHT_WORST = 0.849     # --dbg, the darkest light-theme chip
_BG_DARK_WORST = 0.0255     # --cbg, the lightest dark-theme chip
_CONTRAST = 4.5             # WCAG AA for normal text
_MIN_DARK = _CONTRAST * (_BG_DARK_WORST + 0.05) - 0.05
_MAX_LIGHT = (_BG_LIGHT_WORST + 0.05) / _CONTRAST - 0.05


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
    if slug in TEAMLOGO:
        return f'<span class="tm-{slug}">{esc(name)}</span>'
    return esc(name)


def build_team_logos():
    """slug -> (light logo, dark logo), from teams.csv, for rated teams only.

    Team colours were dropped as distracting; the club logo carries the identity
    instead, exactly as on the NFL card. Only teams the model rates get a rule,
    because teams.csv carries 1,933 schools and a rule for each would add a
    couple of hundred kilobytes to every page for logos that never render.
    """
    if TEAMS is None or "logos" not in TEAMS.columns or "school" not in TEAMS.columns:
        return {}
    want = set()
    try:
        want = {team_slug(t) for t in R.index}
    except Exception:
        want = set()
    out = {}
    for t in TEAMS.itertuples(index=False):
        school = str(getattr(t, "school", "") or "").strip()
        slug = team_slug(school)
        if not school or (want and slug not in want):
            continue
        raw = getattr(t, "logos", None)
        if raw is None or str(raw).strip().lower() in ("", "nan"):
            continue
        try:
            urls = ast.literal_eval(str(raw))
        except Exception:
            continue
        if not isinstance(urls, (list, tuple)):
            continue
        light = next((u for u in urls if "/logos/128/" in u), None)
        dark = next((u for u in urls if "/logos-dark/128/" in u), None)
        if light:
            out[slug] = (light, dark or light)
    return out


TEAMLOGO = build_team_logos()
print(f"team logos: {len(TEAMLOGO)} teams")


def team_css():
    """No colour on team names. A logo in front of each, light or dark to match."""
    return ("".join(f'.tm-{k}{{--logo:url({v[0]})}}' for k, v in TEAMLOGO.items())
            + "".join(f'body.dark .tm-{k}{{--logo:url({v[1]})}}' for k, v in TEAMLOGO.items())
            + '[class^="tm-"]::before,[class*=" tm-"]::before{content:"";display:inline-block;'
              'width:1.15em;height:1.15em;margin-right:.3em;vertical-align:-.22em;'
              'background:var(--logo) center/contain no-repeat}')


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
    # Exact whole-name matches, for cases the school-level table below cannot
    # take safely. Each of these is a school whose short name is also the start
    # of a DIFFERENT school CFBD knows, so only the mascot makes it unambiguous:
    # "UMass" is also the start of UMass Dartmouth and UMass Lowell, and
    # Connecticut, Louisiana State and Southern Methodist each have a defunct
    # second team on record. Matching the whole string cannot collide.
    "connecticut huskies": "UConn",
    "hawaii rainbow warriors": "Hawai'i",      # plain i against CFBD's okina
    "louisiana state tigers": "LSU",
    "southern methodist mustangs": "SMU",
    "umass minutemen": "Massachusetts",
}

# School-level spellings, matched as a prefix and only AFTER the real CFBD names
# have failed, so an alias can never override a genuine name. Built from CFBD's
# own alternateNames and filtered: no abbreviations, nothing that maps to two
# schools, nothing that already resolves, and nothing that is the start of any
# other school CFBD knows in any division. That last rule is the important one.
# It is why "UMass" is not here: it is the start of UMass Dartmouth and UMass
# Lowell, so a prefix match would have quietly joined the wrong team, which is
# the failure this whole resolver exists to prevent.
#
# The card reported three of these live before they were added: Appalachian
# State, San Jose State and UMass, all FBS, all silently dropped. They only
# surfaced when those teams first carried a quote, which is why the table is
# built from the whole team file rather than from whatever failed this week.
ODDS_SCHOOL_ALIAS = {
    "abilene chrstn": "Abilene Christian",
    "alabama st": "Alabama State",
    "alabama-birmingham": "UAB",
    "alcorn": "Alcorn State",
    "alcorn st": "Alcorn State",
    "appalachian state": "App State",
    "ar-pine bluff": "Arkansas-Pine Bluff",
    "arizona st": "Arizona State",
    "arkansas pine bluff": "Arkansas-Pine Bluff",
    "arkansas st": "Arkansas State",
    "bethune": "Bethune-Cookman",
    "boise st": "Boise State",
    "brigham young": "BYU",
    "c arkansas": "Central Arkansas",
    "c connecticut": "Central Connecticut",
    "c michigan": "Central Michigan",
    "cal state sacramento": "Sacramento State",
    "california-davis": "UC Davis",
    "central florida": "UCF",
    "charleston so": "Charleston Southern",
    "coastal": "Coastal Carolina",
    "colorado st": "Colorado State",
    "delaware st": "Delaware State",
    "dixie state": "Utah Tech",
    "e illinois": "Eastern Illinois",
    "e kentucky": "Eastern Kentucky",
    "e michigan": "Eastern Michigan",
    "e washington": "Eastern Washington",
    "florida intl": "Florida International",
    "florida st": "Florida State",
    "fresno st": "Fresno State",
    "ga southern": "Georgia Southern",
    "gardner webb": "Gardner-Webb",
    "georgia st": "Georgia State",
    "hou christian": "Houston Christian",
    "houston baptist": "Houston Christian",
    "idaho st": "Idaho State",
    "illinois st": "Illinois State",
    "indiana st": "Indiana State",
    "jackson st": "Jackson State",
    "jax state": "Jacksonville State",
    "kansas st": "Kansas State",
    "kennesaw": "Kennesaw State",
    "kennesaw st": "Kennesaw State",
    "la.-monroe": "UL Monroe",
    "long island": "Long Island University",
    "miami oh": "Miami (OH)",
    "michigan st": "Michigan State",
    "miss valley st": "Mississippi Valley State",
    "mississippi st": "Mississippi State",
    "missouri st": "Missouri State",
    "montana st": "Montana State",
    "morehead st": "Morehead State",
    "morgan st": "Morgan State",
    "murray st": "Murray State",
    "n arizona": "Northern Arizona",
    "n colorado": "Northern Colorado",
    "n dakota st": "North Dakota State",
    "n illinois": "Northern Illinois",
    "n'western st": "Northwestern State",
    "nc central": "North Carolina Central",
    "nevada-las vegas": "UNLV",
    "new mexico st": "New Mexico State",
    "norfolk st": "Norfolk State",
    "north carolina st.": "NC State",
    "oklahoma st": "Oklahoma State",
    "oregon st": "Oregon State",
    "portland st": "Portland State",
    "prairie view": "Prairie View A&M",
    "s dakota st": "South Dakota State",
    "s illinois": "Southern Illinois",
    "sacramento st": "Sacramento State",
    "san diego st": "San Diego State",
    "san jose st.": "San José State",
    "san jose state": "San José State",
    "san josé st": "San José State",
    "sc state": "South Carolina State",
    "se missouri": "Southeast Missouri State",
    "sf austin": "Stephen F. Austin",
    "southeast louisiana": "SE Louisiana",
    "southeast missouri": "Southeast Missouri State",
    "southern mississippi": "Southern Miss",
    "st thomas": "St. Thomas (MN)",
    "st thomas mn": "St. Thomas (MN)",
    "stephen f austin": "Stephen F. Austin",
    "suny albany": "UAlbany",
    "tarleton st": "Tarleton State",
    "tennessee martin": "UT Martin",
    "tennessee st": "Tennessee State",
    "texas a&m-commerce": "East Texas A&M",
    "texas christian": "TCU",
    "texas st": "Texas State",
    "texas-el paso": "UTEP",
    "texas-san antonio": "UTSA",
    "ul lafayette": "Louisiana",
    "ut rio grande": "UT Rio Grande Valley",
    "virginia military institute": "VMI",
    "w carolina": "Western Carolina",
    "w illinois": "Western Illinois",
    "w michigan": "Western Michigan",
    "washington st": "Washington State",
    "weber st": "Weber State",
    "western ky": "Western Kentucky",
    "youngstown st": "Youngstown State",
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
    alias_len = sorted(ODDS_SCHOOL_ALIAS, key=len, reverse=True)
    cache = {}

    def resolve(name):
        n = str(name).strip()
        if n in cache:
            return cache[n]
        low = n.lower()
        # 1. an exact whole-name statement wins outright
        out = ODDS_ALIAS.get(low)
        # 2. then the real CFBD names, longest first
        if out is None:
            for c in by_len:
                if n == c or n.startswith(c + " "):
                    out = c
                    break
        # 3. only then the alternate spellings, so an alias can never take a
        #    name that belongs to a real team
        if out is None:
            for a in alias_len:
                if low == a or low.startswith(a + " "):
                    out = ODDS_SCHOOL_ALIAS[a]
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
# Scope is FBS and FCS, both divisions, in every pairing. The old rule kept only
# games with at least one FBS side, which dropped about 55 FCS games a week. It
# rested on an assumption that was never tested: measured over 1,956 priced
# FCS-against-FCS games, our error is 13.10 against the market's 11.93, where
# the FBS gap is 12.80 against 12.18. The groups block in model_state.json holds
# those figures. Divisions II and III stay out: no market, and a schedule that
# barely touches the top two.
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
        # FBS when both sides are FBS, FCS when neither is, Cross when they
        # differ. Scope keeps at least one FBS side, so FCS only appears if the
        # schedule ever gives one; the filter lists only what is on the page.
        div=("FBS" if (hd == "fbs" and ad == "fbs") else
             ("FCS" if (hd != "fbs" and ad != "fbs") else "Cross")),
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
# last_number is the market's number for this same side as of the most recent
# run BEFORE kickoff. Once the game starts nothing updates it again, so it is
# the closing number. "number" still holds what the pick was issued at and is
# never rewritten: the pair is what closing line value is measured from.
PCOLS = ["season", "week", "away", "home", "market", "strategy", "tier", "grade",
         "side", "number", "book", "issued_utc", "result", "settled_utc",
         "last_number", "last_seen_utc"]
pk = pd.read_csv(PICKS_PATH) if os.path.exists(PICKS_PATH) else pd.DataFrame(columns=PCOLS)
for c in PCOLS:
    if c not in pk.columns:
        pk[c] = None
# An all-empty column reads back as float64, and writing "win" into it raises.
# The first settled pick of the season would otherwise crash the nightly run.
for c in ("result", "settled_utc", "tier", "grade", "side", "book",
          "market", "strategy", "away", "home", "issued_utc", "last_seen_utc"):
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
                           v["side"], v["number"], book, NOW.isoformat(), None, None,
                           v["number"], NOW.isoformat()]
        existing.add(key)
        issued += 1

# Closing line value needs the market's number at the close, which is simply
# the last number seen before kickoff. So on every pre-kickoff run each pick
# already on file has its last_number refreshed from today's market; once the
# game starts the loop skips it and the value freezes. Nothing rewrites the
# number the pick was issued at.
_MKT_NOW = {}
for _r in rows:
    if _r.get("started"):
        continue
    _mk, _pp = PICKS_BY_GAME.get((_r["away"], _r["home"]), ({}, []))
    for _name, _v in (_mk or {}).items():
        if _v.get("number") is not None:
            _MKT_NOW[(str(_r["away"]), str(_r["home"]), _name, str(_v.get("side", "")))] = _v["number"]
    for _p in (_pp or []):
        if _p.get("number") is not None:
            _MKT_NOW[(str(_r["away"]), str(_r["home"]), "price", str(_p.get("side", "")))] = _p["number"]

_moved = 0
for _i, _row in pk.iterrows():
    if isinstance(_row.get("result"), str) and _row.get("result"):
        continue
    _key = (str(_row["away"]), str(_row["home"]), str(_row["market"]), str(_row["side"]))
    _now = _MKT_NOW.get(_key)
    if _now is None:
        continue
    try:
        if float(_row.get("last_number")) == float(_now):
            continue
    except (TypeError, ValueError):
        pass
    pk.at[_i, "last_number"] = _now
    pk.at[_i, "last_seen_utc"] = NOW.isoformat()
    _moved += 1
if _moved:
    print(f"  closing numbers: {_moved} open pick(s) re-marked at today's market")

_k_season = _k(season)

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
PK_ALL = pk.copy()

# ---- line watch -------------------------------------------------------------
# Most FCS games show no line on the day the card is built, and the picks file
# cannot answer whether CFBD posts those lines before kickoff or backfills them
# afterwards: in a finished week the two look identical. So every run appends
# what it could see at that moment, by group, with how many hours were left
# before the first kickoff in that group. Read down the rows and the answer is
# plain. Costs nothing: the lines are pulled every run anyway.
try:
    _lw = os.path.join(DOCS, "line_watch.csv")
    _seen, _hrs = {}, {}
    for _r in rows:
        _g = str(_r.get("div", ""))
        if not _g:
            continue
        _d = _seen.setdefault(_g, [0, 0])
        _d[0] += 1
        if _r.get("mkt") is not None:
            _d[1] += 1
        # NOT _k: that is the module-level key helper, and binding a string to
        # it here broke every pick written after this block. See 4.3k.
        _kick = _r.get("kick")
        if _kick:
            try:
                _h = round((pd.Timestamp(_kick) - NOW).total_seconds() / 3600.0, 1)
                if _g not in _hrs or _h < _hrs[_g]:
                    _hrs[_g] = _h
            except Exception:
                pass
    _new = pd.DataFrame([
        dict(run_utc=NOW.isoformat(timespec="minutes"),
             mode=os.environ.get("CFB_MODE", "manual"), season=_k_season, week=WEEK,
             group=_g, games=_v[0], priced=_v[1], hours_to_first_kick=_hrs.get(_g, ""))
        for _g, _v in sorted(_seen.items())])
    _old = pd.read_csv(_lw) if os.path.exists(_lw) else pd.DataFrame()
    pd.concat([_old, _new], ignore_index=True).to_csv(_lw, index=False)
    print("  line watch: " + ", ".join(f"{g} {v[1]}/{v[0]} priced" for g, v in sorted(_seen.items())))
except Exception as _e:
    print(f"  line watch: not recorded ({_e})")
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


# --------------------------------------------------------------- news log
# Does the weekly research add anything? Nothing in either repo can answer that
# today, and a season of rows is the only way it ever will. The specification is
# written once and shared with the NFL card: same filename, same columns, same
# order. If the two drift by one character the comparison is worthless and
# nobody finds out until they try it, which is 4.3n.
#
# The research writes only what the card cannot know for itself: whether a
# starting quarterback is out, how many starters are out, and how well sourced
# that is. Every number here comes from the card's own feed, because asking the
# research to retype a line the card already holds is 4.3h.
#
# Append-only, and written BEFORE kickoff exactly as picks.csv is. A row
# recorded once the result is known is worthless (4.3e), and never rewriting a
# row keeps the state at the time it was written even as the line moves later
# in the week.
NEWSLOG_PATH = os.path.join(DOCS, "newslog.csv")
NLCOLS = ["written_utc", "season", "week", "away", "home",
          "qb_out", "starters_out", "confidence",
          "spread_open", "spread_at_write", "total_open", "total_at_write",
          "our_number"]
nlog = pd.read_csv(NEWSLOG_PATH) if os.path.exists(NEWSLOG_PATH) else pd.DataFrame(columns=NLCOLS)
for _c in NLCOLS:
    if _c not in nlog.columns:
        nlog[_c] = None
# A game may appear more than once, and that is the point. Writing one row per
# game and never again looked right and collected nothing: the card rebuilds
# Sunday morning and the research lands Tuesday, so every row would have been
# stamped with an empty research block before the research existed, forever.
# So a row is written the first time a game is seen before kickoff, and again
# whenever the research block CHANGES. The last pre-kickoff row for a game is
# the one to analyse. Append-only either way; nothing already written is edited.
def _nlfp(qb, starters, conf):
    """One string standing for a research block.

    Read back from CSV an integer 3 returns as 3.0, so comparing the raw values
    would report a change on every run and append a row every run. Everything is
    normalised through here, on both sides of the comparison."""
    def one(v):
        if v is None:
            return ""
        try:
            if pd.isna(v):
                return ""
        except Exception:
            pass
        try:
            return str(int(float(v)))
        except Exception:
            return str(v).strip()
    return f"{one(qb)}|{one(starters)}|{one(conf)}"

# The research block as the LAST row for each game recorded it. Same key
# spelling on both sides of the comparison, for the reason pkey exists.
_nlast = {}
for _r in nlog.itertuples():
    try:
        if int(_r.season) == int(season) and int(_r.week) == int(WEEK):
            _nlast[pkey(season, WEEK, _r.away, _r.home)] = _nlfp(
                _r.qb_out, _r.starters_out, _r.confidence)
    except Exception:
        continue
_nnew = []
for r in rows:
    _started = bool(r["final"])
    if r["kick"]:
        try:
            _started = _started or datetime.fromisoformat(r["kick"]) <= NOW
        except Exception:
            pass
    if _started:
        continue
    _nk = pkey(season, WEEK, r["away"], r["home"])
    _lg = (r["notes"] or {}).get("log") or {}
    if not isinstance(_lg, dict):
        _lg = {}
    _nqb = str(_lg.get("qb_out", "") or "")
    _nst = _lg.get("starters_out")
    _ncf = str(_lg.get("confidence", "") or "")
    if _nk in _nlast and _nlast[_nk] == _nlfp(_nqb, _nst, _ncf):
        continue
    _nnew.append(dict(
        written_utc=NOW.isoformat(), season=season, week=WEEK,
        away=r["away"], home=r["home"],
        qb_out=_nqb, starters_out=_nst, confidence=_ncf,
        spread_open=r["open_mkt"], spread_at_write=r["mkt"],
        total_open=r["open_total"], total_at_write=r["mkt_total"],
        our_number=r["model"]))
    _nlast[_nk] = _nlfp(_nqb, _nst, _ncf)
if _nnew:
    nlog = pd.concat([nlog, pd.DataFrame(_nnew)], ignore_index=True)
nlog = nlog[NLCOLS]
# A count written as 3.0 is the same number but a worse file to read. The
# nullable integer type keeps 3 as 3 and a missing block as empty, rather than
# forcing the column to float the moment one row has no block.
nlog["starters_out"] = pd.to_numeric(nlog["starters_out"],
                                     errors="coerce").astype("Int64")
nlog.to_csv(NEWSLOG_PATH, index=False)
_withlog = sum(1 for d in _nnew if d["qb_out"] or d["confidence"]
               or d["starters_out"] is not None)
print(f"news log: {len(nlog)} rows on file, {len(_nnew)} written this run, "
      f"{_withlog} of them carrying a research block")


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
    no_line = [r for r in rows if r["mkt"] is None]
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
    # How old is every fetched dataset? fetch_data.py records both the time it
    # pulled each one and that dataset's own maximum age, so this compares them
    # without restating a single number. A dataset that is reused rather than
    # refetched is only correct while the refresh that should replace it keeps
    # happening; if that stops, nothing errors and the page looks healthy.
    try:
        with open(P("fetched.json")) as _ff:
            _fresh = json.load(_ff)
    except Exception:
        _fresh = None
    if not _fresh:
        out.append(("no fetch log",
                    "scripts/data/fetched.json is missing, so nothing on this page "
                    "carries a fetch date and no dataset can be checked for being "
                    "overdue. Every dataset will also be refetched at full cost on "
                    "the next run."))
    else:
        _overdue = []
        for _n, _e in sorted(_fresh.items()):
            _at = _e.get("at") if isinstance(_e, dict) else _e
            _max = _e.get("max_age_days") if isinstance(_e, dict) else None
            if not _at or not _max:
                continue
            try:
                _w = datetime.fromisoformat(str(_at))
                if _w.tzinfo is None:
                    _w = _w.replace(tzinfo=timezone.utc)
                _age = (NOW - _w).total_seconds() / 86400.0
            except Exception:
                continue
            if _age > float(_max):
                _overdue.append(f"{_n} {_age:.1f}d old against a {float(_max):g}d limit")
        if _overdue:
            out.append(("stale data",
                        "A refresh that should have happened did not: "
                        + "; ".join(_overdue) + "."))
    if not NOTES:
        out.append(("no research",
                    "scripts/notes.json is missing, so no game on this card carries "
                    "injury, coaching or line-movement context. Section 4.2 says the "
                    "model does not beat the market on public data alone, and this is "
                    "the data it is missing."))
    elif rows:
        _have = sum(1 for r in rows if r.get("notes"))
        if _have == 0:
            # Which week is it actually for? Written ahead of time is normal and
            # good; written for a week already played is the real problem. Say
            # which, rather than crying stale at a file that is simply early.
            _wk = {}
            for _, _g in CUR.iterrows():
                _k = f"{_g.away_team}@{_g.home_team}"
                if _k in NOTES and pd.notna(_g.get("week")):
                    _w = int(_g["week"]); _wk[_w] = _wk.get(_w, 0) + 1
            if not _wk:
                out.append(("research stale",
                            f"notes.json holds {len(NOTES)} games and not one of them is "
                            f"on this season's schedule. The keys are wrong."))
            else:
                _best = max(_wk, key=_wk.get)
                _when = "ahead of" if _best > WEEK else "behind"
                out.append(("research week",
                            f"notes.json holds research for {_wk[_best]} week {_best} "
                            f"games, and this card is showing week {WEEK}. It is "
                            f"{_when} the card. "
                            + ("It will appear when the card rolls forward."
                               if _best > WEEK else
                               "It needs replacing with this week's research.")))
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


def slate_of(local_hhmm):
    """Which part of the day a kickoff falls in, in Phoenix time.

    Morning before noon, afternoon until 5pm, late after that. Clock time, not
    a measured thing: this is for finding the games you can actually watch.
    The NFL card uses the same three buckets and the same boundaries.
    """
    try:
        h = int(str(local_hhmm)[:2])
    except (TypeError, ValueError):
        return ""
    return "Morning" if h < 12 else ("Afternoon" if h < 17 else "Late")


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
    """The NFL card's last column: what is odd about this game, if anything.

    Returns a LIST, one note per line, empty when there is nothing to say. The
    NFL card leaves that cell blank rather than writing "nothing unusual",
    because a column of filler reads as content and the eye has to check each
    row to find out it says nothing. Blank is the honest answer.
    """
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
    return notes


def summary_table():
    """The NFL card's summary table, column for column.

    Date, day and time, game, then each market as both sides with the called
    side picked out, its grade beside it, and one plain-English column at the
    end. Seventeen columns had grown up here, four of them per market, and it
    was no longer obvious which grade belonged to which bet. The two college
    readings that the NFL card has no equivalent for -- confidence, and value
    over the price -- ride under the grade rather than in columns of their own.
    """
    body, days, gids, slates = [], [], [], []
    for r in rows:
        if r["final"]:
            continue
        mk, pp = PICKS_BY_GAME.get((r["away"], r["home"]), ({}, []))
        sp, ml, tt = mk.get("spread"), mk.get("moneyline"), mk.get("total")
        date, day, time = phx_parts(r["kick"])
        gid = f'{r["away"]}@{r["home"]}'
        if day and day not in days:
            days.append(day)
        gids.append((gid, r["away"], r["home"]))
        _sl = slate_of(time)
        if _sl and _sl not in slates:
            slates.append(_sl)

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

        def side_cell(home_team, home_num, away_team, away_num, home_is_pick, v):
            """Both sides of the market. The called one sits on its grade's shade,
            with the team name still in the team's own colour inside it."""
            if not v or v.get("number") is None:
                return '<td class="grp num">&mdash;</td>'
            pc = PK.get(v.get("grade", "D"), "pk-d")

            def side(team, num, picked):
                if picked:
                    return f'<span class="{pc}">{tm(team)} {esc(num)}</span>'
                return f'<span class="num">{esc(team)} {esc(num)}</span>'

            h = side(home_team, home_num, home_is_pick)
            a = side(away_team, away_num, not home_is_pick)
            return f'<td class="grp">{h} <span class="num">/</span> {a}</td>'

        if sp and r["mkt"] is not None:
            sp_td = side_cell(r["home"], f'{-r["mkt"]:+.1f}',
                              r["away"], f'{r["mkt"]:+.1f}',
                              sp["side"] == r["home"], sp)
        else:
            sp_td = '<td class="grp num">&mdash;</td>'

        if ml and r["home_ml"] is not None and r["away_ml"] is not None:
            ml_td = side_cell(r["home"], f'{int(r["home_ml"]):+d}',
                              r["away"], f'{int(r["away_ml"]):+d}',
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
        read_td = f'<td class="grp rd">{"<br>".join(esc(n) for n in reads)}</td>' 

        body.append(
            f'<tr class="row" data-day="{esc(day)}" data-gid="{esc(gid)}" '
            f'data-slate="{esc(slate_of(time))}" data-div="{esc(str(r.get("div", "")))}">'
            f'<td class="num">{esc(date)}</td>'
            f'<td class="num">{esc(day)} {esc(time)}</td>'
            f'<td class="game">{tm(r["away"])} <span class="num">@</span> '
            f'{tm(r["home"])}</td>'
            + sp_td + gcell(sp) + ml_td + gcell(ml) + tot_td + pick_td + gcell(tt)
            + read_td + '</tr>')

    if not body:
        return '<p class="muted">No in-scope games left to play this week.</p>'

    flt = ['<div class="filters">'
           '<details class="fdrop"><summary><b>Day</b><span class="fsum">all</span>'
           '</summary><div class="fpop">']
    for d in days:
        flt.append(f'<label><input type="checkbox" class="fd" value="{esc(d)}" '
                   f'checked onchange="flt()">{esc(d)}</label>')
    flt.append('</div></details>'
               '<details class="fdrop"><summary><b>Slate</b><span class="fsum">all</span>'
               '</summary><div class="fpop">')
    for sl in ("Morning", "Afternoon", "Late"):
        if sl in slates:
            flt.append(f'<label><input type="checkbox" class="fsl" value="{sl}" '
                       f'checked onchange="flt()">{sl}</label>')
    flt.append('</div></details>'
               '<details class="fdrop"><summary><b>Division</b><span class="fsum">all</span>'
               '</summary><div class="fpop">')
    for dv in ("FBS", "Cross", "FCS"):
        if any(str(r.get("div", "")) == dv for r in rows):
            lab = "Cross-division" if dv == "Cross" else dv
            flt.append(f'<label><input type="checkbox" class="fdv" value="{dv}" '
                       f'checked onchange="flt()">{lab}</label>')
    flt.append('</div></details>'
               '<details class="fdrop"><summary><b>Game</b><span class="fsum">all</span>'
               '</summary><div class="fpop">')
    for gid, a, h in gids:
        flt.append(f'<label><input type="checkbox" class="fgm" value="{esc(gid)}" '
                   f'checked onchange="flt()">{esc(a)} @ {esc(h)}</label>')
    flt.append('</div></details><div class="fg"><b>&nbsp;</b>'
               '<button onclick="allOn()">Select all</button> '
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


# A publication is not a person with a record, and a model is not an expert.
# Entries named as a consensus, a model or a relay of someone else's picks are
# dropped from the page, because no record can ever attach to them. Same rule
# and same wording as the NFL card.
_UNATTRIB = ("consensus", "(via ", " via ", "projection model", " model ",
             "model backs", "staff pick", "expert panel", "experts)")


def _expert_ok(e):
    nm = str((e or {}).get("name", "")).strip().lower()
    if not nm or any(p in nm for p in _UNATTRIB):
        return False
    return not nm.endswith(" model")


def _expert_struct(e, away, home):
    """The trackable form of one pick, or None with the reason why not."""
    mk = str(e.get("market", "")).strip().lower()
    if not mk:
        return None, "no market"
    if mk not in ("spread", "total", "moneyline"):
        return None, f"market '{mk}' is not spread, total or moneyline"
    sd = str(e.get("side", "")).strip()
    if mk == "total":
        sd = sd.lower()
        if sd not in ("over", "under"):
            return None, "a total pick needs side over or under"
    else:
        slug = team_slug(sd)
        if slug == team_slug(away):
            sd = away
        elif slug == team_slug(home):
            sd = home
        else:
            return None, f"side '{e.get('side')}' is not a team in this game"
    ln = e.get("line")
    if mk in ("spread", "total"):
        try:
            ln = float(ln)
        except (TypeError, ValueError):
            return None, "no numeric line"
        if ln != ln:
            return None, "no numeric line"
    else:
        ln = None
    return dict(market=mk, side=sd, line=ln), ""


def _expert_result(market, side, line, away, home, a_pts, h_pts):
    if market == "total":
        m = (a_pts + h_pts) - line
        m = m if side == "over" else -m
    else:
        m = (h_pts - a_pts) if side == home else (a_pts - h_pts)
        if market == "spread":
            m = m + line
    return "W" if m > 0 else ("L" if m < 0 else "P")


def track_experts():
    """Log every structured expert pick before kickoff and settle the finished ones.

    Most outlets publish no running record for a college writer, so a pick with
    "record not published" beside it every week tells the reader nothing. The
    card keeps the record itself. Two rules, the same as the picks ledger:
    nothing is written once a game has started, and a row is added only when a
    pick is new or its side or line changed. Results are worked out from the
    schedule on every run rather than stored, so no score lives in two files.
    """
    cols = ["first_seen_utc", "season", "week", "game", "name",
            "market", "side", "line", "pick"]
    path = os.path.join(DOCS, "expert_picks.csv")
    old = pd.DataFrame(columns=cols)
    if os.path.exists(path):
        try:
            old = pd.read_csv(path)
        except Exception:
            ISSUES.append(("expert picks",
                           "docs/expert_picks.csv could not be read, so no expert record "
                           "is shown and nothing new was written this run."))
            return {}
    for c in cols:
        if c not in old.columns:
            old[c] = None

    def fp(side, line):
        try:
            l = "" if line is None or float(line) != float(line) else f"{float(line):g}"
        except (TypeError, ValueError):
            l = str(line)
        return f"{side}|{l}"

    last = {}
    for t in old.itertuples():
        try:
            last[(str(t.game), str(t.name), str(t.market))] = fp(t.side, t.line)
        except Exception:
            continue

    games = {}
    for g in G.itertuples():
        key = f"{g.away_team}@{g.home_team}"
        done = pd.notna(getattr(g, "away_points", None)) and pd.notna(getattr(g, "home_points", None))
        games[key] = dict(week=int(g.week) if pd.notna(g.week) else 0,
                          kick=g.start_date, done=done,
                          a=(float(g.away_points) if done else None),
                          h=(float(g.home_points) if done else None))
    now = pd.Timestamp.now(tz="UTC")
    new, untracked, dropped = [], [], []
    for gid, n in NOTES.items():
        ex = (n or {}).get("experts") or []
        if not isinstance(ex, list) or gid not in games:
            continue
        gm = games[gid]
        away, home = gid.split("@")
        started = gm["done"] or (pd.notna(gm["kick"]) and gm["kick"] <= now)
        for e in ex:
            if not isinstance(e, dict):
                continue
            if not _expert_ok(e):
                dropped.append(f"{gid}: {e.get('name', '')}")
                continue
            st, why = _expert_struct(e, away, home)
            if st is None:
                if not started:
                    untracked.append(f"{gid} {e.get('name', '')} ({why})")
                continue
            if started:
                continue
            key = (gid, str(e["name"]).strip(), st["market"])
            if last.get(key) == fp(st["side"], st["line"]):
                continue
            new.append(dict(first_seen_utc=now.isoformat(timespec="seconds"),
                            season=int(CUR.season.max()) if "season" in CUR.columns and len(CUR) else 0,
                            week=gm["week"], game=gid,
                            name=str(e["name"]).strip(), market=st["market"],
                            side=st["side"], line=st["line"], pick=str(e.get("pick", ""))))
            last[key] = fp(st["side"], st["line"])
    out = pd.concat([old, pd.DataFrame(new)], ignore_index=True) if new else old
    if len(out) or os.path.exists(path):
        out[cols].to_csv(path, index=False)

    if dropped:
        ISSUES.append(("expert picks",
                       f"{len(dropped)} expert entr(ies) name a model, a consensus or a "
                       f"relayed publication rather than a person, so they are left off the "
                       f"page: {'; '.join(dropped[:4])}."))
    if untracked:
        ISSUES.append(("expert picks",
                       f"{len(untracked)} expert pick(s) show on the page but cannot build a "
                       f"record, because they carry no market, side and line: "
                       f"{'; '.join(untracked[:4])}."))

    def _as_text(market, side, line):
        """A pick the way the expert wrote it: side and the line they took."""
        try:
            ln = float(line)
        except (TypeError, ValueError):
            ln = None
        if market == "total":
            word = "Over" if str(side).lower().startswith("o") else "Under"
            return f"{word} {ln:g}" if ln is not None else word
        if market == "moneyline":
            return f"{side} ML"
        return f"{side} {ln:+g}" if ln is not None else str(side)

    weekly, tally = {}, {}
    if len(out):
        o = out.sort_values("first_seen_utc").groupby(["game", "name", "market"]).tail(1)
        for t in o.itertuples():
            gm = games.get(str(t.game))
            # This week's picks, settled or not: what each writer is on right now,
            # at the line they took. The NFL card shows the same column.
            try:
                if gm and int(t.week) == WEEK:
                    weekly.setdefault(str(t.name), []).append(
                        dict(game=str(t.game), market=str(t.market), side=str(t.side),
                             line=t.line, text=_as_text(str(t.market), str(t.side), t.line)))
            except Exception:
                pass
            if not gm or not gm["done"]:
                continue
            aw, hm = str(t.game).split("@")
            try:
                ln = float(t.line) if str(t.market) != "moneyline" else None
            except (TypeError, ValueError):
                continue
            res = _expert_result(str(t.market), str(t.side), ln, aw, hm, gm["a"], gm["h"])
            d = tally.setdefault(str(t.name), {}).setdefault(str(t.market), [0, 0, 0])
            d["WLP".index(res)] += 1
    print(f"expert picks: {len(out)} rows on file, {len(new)} written this run, "
          f"{len(dropped)} unattributed dropped, {len(untracked)} not trackable")
    for k in weekly:
        weekly[k] = sorted(weekly[k], key=lambda d: (d["game"], d["market"]))
    return tally, weekly


EXPERT_TALLY, EXPERT_WEEK = track_experts()


def _card_picks():
    """The card's own call per game and market this week, with the grade it carries.

    Used to mark an expert pick that lands on the same side. The grade on the
    stripe is the CARD's, not the expert's: it says "we agree, and this is how
    strongly we hold it".
    """
    out = {}
    for (away, home), (mk, _pp) in PICKS_BY_GAME.items():
        gid = f"{away}@{home}"
        for market, v in (mk or {}).items():
            side = str((v or {}).get("side", "")).strip()
            grade = str((v or {}).get("grade", "")).strip().upper()[:1]
            if not side:
                continue
            if str(market).lower() == "total":
                side = "over" if side.lower().startswith("o") else "under"
            out[(gid, str(market).lower())] = (side.lower(), grade)
    return out


CARD_PICKS = _card_picks()


def agree_grade(pick):
    """The card's grade when it is on the same side as this expert pick, else ''.

    Side only. Taking the same team at a different number is still the same
    call, and the expert's own line is shown beside it either way.
    """
    got = CARD_PICKS.get((pick.get("game", ""), str(pick.get("market", "")).lower()))
    if not got:
        return ""
    side, grade = got
    mine = str(pick.get("side", "")).lower()
    if str(pick.get("market", "")).lower() == "total":
        mine = "over" if mine.startswith("o") else "under"
    return grade if mine == side and grade in ("A", "B", "C", "D") else ""


def expert_short(name):
    m = EXPERT_TALLY.get(str(name).strip()) or {}
    bits = []
    for mk, lbl in (("spread", "ATS"), ("total", "totals"), ("moneyline", "SU")):
        if mk in m:
            w, l, p = m[mk]
            bits.append(f"{w}-{l}" + (f"-{p}" if p else "") + f" {lbl}")
    return ", ".join(bits)


def clv_block():
    """Closing line value: did the market move toward the side we took.

    Measured from two numbers the picks file already holds: "number", what the
    pick was issued at, and "last_number", the market's number on the last run
    before kickoff, which is the close. Nothing here says the model is right;
    it says whether the market agreed with it afterwards, which is a different
    and much easier question.

    Spread and total are in points, taken from the side's own point of view, so
    a positive figure means the number we took was better than the close.
    Moneyline is in percentage points of implied probability, de-vigged nowhere,
    so it is a rough read and is reported on its own rather than mixed in.

    Only settled picks count, and only where both numbers are present. Picks
    settled before this was built have no closing number and are left out, which
    is why the count here is smaller than the record above.
    """
    if not len(PK_ALL):
        return ''
    d = PK_ALL[PK_ALL.result.isin(["win", "loss", "push"])].copy()
    rows, ml = [], []
    for t in d.itertuples():
        try:
            took, close = float(t.number), float(t.last_number)
        except (TypeError, ValueError):
            continue
        if took != took or close != close:
            continue
        mkt = str(t.market).lower()
        if mkt == "moneyline":
            def imp(a):
                a = float(a)
                return (-a / (-a + 100.0)) if a < 0 else (100.0 / (a + 100.0))
            ml.append(100.0 * (imp(close) - imp(took)))
            continue
        if mkt == "total":
            side = str(t.side).lower()
            val = (close - took) if side.startswith("o") else (took - close)
        else:
            val = took - close
        rows.append(val)
    if not rows and not ml:
        return ('<h3 id="clv">Closing line value</h3><div class="card none">No settled pick '
                'has a closing number yet. The card started recording them on this run, so '
                'this fills in as games finish from here.</div>')
    def line(label, vals, unit):
        n = len(vals)
        if not n:
            return ''
        toward = sum(1 for v in vals if v > 0)
        away = sum(1 for v in vals if v < 0)
        avg = sum(vals) / n
        return (f'<tr><td>{label}</td><td class="num">{n}</td>'
                f'<td class="num">{toward} ({100*toward/n:.0f}%)</td>'
                f'<td class="num">{away}</td>'
                f'<td class="num">{avg:+.2f} {unit}</td></tr>')
    body = line("Spread, total and price", rows, "pts") + line("Moneyline", ml, "pts of win%")
    return ('<h3 id="clv">Closing line value</h3>'
            '<div class="card">Whether the market moved toward the side we took between the '
            'pick being issued and kickoff. It is not a record and it is not profit: a pick '
            'can beat the close and still lose. It is the one question that does not depend '
            'on being right about the game. Picks settled before the card began recording '
            'closing numbers are left out.</div>'
            '<div class="scroll"><table class="sheet"><thead><tr><th>Market</th>'
            '<th>Settled with both numbers</th><th>Moved toward us</th><th>Moved away</th>'
            '<th>Average move</th></tr></thead><tbody>' + body + '</tbody></table></div>')


def changes_html():
    """The games whose research changed since the previous run, folded away."""
    if not CHANGES:
        if NOTES and PREV_TS:
            return ('<div class="card none">No changes since the notes saved '
                    f'{esc(str(PREV_TS).replace("T", " "))}.</div>')
        return '<div class="card none">No previous notes to compare against yet.</div>'
    lbl = {"injuries": "Injuries", "returning": "Returning from injury",
           "trades": "Transfers &amp; roster moves", "coaching": "Coaching",
           "suspensions": "Suspensions", "movement": "Line movement",
           "notable": "Notable", "experts": "Expert picks"}

    def fmt(v):
        try:
            d = json.loads(v)
            if isinstance(d, dict):
                return (f'<b>{esc(str(d.get("name", "")))}</b> '
                        f'({esc(str(d.get("record", "record n/a")))}) &mdash; '
                        f'{esc(str(d.get("pick", "")))}')
        except Exception:
            pass
        return esc(str(v))

    n_add = sum(len(v["added"]) for v in CHANGES.values())
    n_rem = sum(len(v["removed"]) for v in CHANGES.values())
    out = [f'<div class="card"><b>{len(CHANGES)} game(s) changed</b> &mdash; {n_add} item(s) '
           f'added, {n_rem} removed'
           + (f', against the notes saved {esc(str(PREV_TS).replace("T", " "))}.' if PREV_TS else '.')
           + ' Games not listed here are unchanged.</div>']
    for g, c in CHANGES.items():
        aw, hm = (g.split("@") + ["", ""])[:2]
        tag = (' <span class="sp">new game</span>' if c["new_game"] else
               (' <span class="sp">no longer in notes</span>' if c["dropped"] else ''))
        secs = []
        for sec, _v in c["added"]:
            if lbl.get(sec, sec) not in secs:
                secs.append(lbl.get(sec, sec))
        gist = f'{len(c["added"])} added' if c["added"] else ''
        if c["removed"]:
            gist += (", " if gist else "") + f'{len(c["removed"])} removed'
        if secs:
            gist += " &mdash; " + ", ".join(secs[:3]) + ("..." if len(secs) > 3 else "")
        out.append(f'<details class="card chg"><summary>{tm(aw)}'
                   f'<span class="vs">at</span>{tm(hm)}{tag}'
                   f'<span class="chgGist">{gist}</span></summary>')
        if c["added"]:
            out.append('<div class="lbl">Added</div><ul class="nl">' + "".join(
                f'<li><span class="chgA">+</span> <i>{lbl.get(sec, sec)}</i> &mdash; {fmt(v)}</li>'
                for sec, v in c["added"]) + '</ul>')
        if c["removed"]:
            out.append('<div class="lbl">Removed</div><ul class="nl">' + "".join(
                f'<li><span class="chgR">&minus;</span> <i>{lbl.get(sec, sec)}</i> &mdash; {fmt(v)}</li>'
                for sec, v in c["removed"]) + '</ul>')
        out.append('</details>')
    return "".join(out)


def expert_table():
    """Every tracked expert, ranked, with what their record actually supports."""
    # Render as soon as anyone has a pick this week, not only once picks have
    # settled: the point of the column is to show what they are on now.
    if not EXPERT_TALLY and not EXPERT_WEEK:
        return ''
    rows = []
    for nm in dict.fromkeys(list(EXPERT_TALLY) + list(EXPERT_WEEK)):
        m = EXPERT_TALLY.get(nm) or {}
        sp, to, su = m.get("spread"), m.get("total"), m.get("moneyline")
        w = (sp or [0, 0, 0])[0] + (to or [0, 0, 0])[0]
        l = (sp or [0, 0, 0])[1] + (to or [0, 0, 0])[1]
        p = (sp or [0, 0, 0])[2] + (to or [0, 0, 0])[2]
        rows.append(((100 * w / (w + l) if w + l else -1.0, w - l, w + l,
                      len(EXPERT_WEEK.get(nm) or [])), nm, sp, to, su, w, l, p))
    def cell(v):
        return "&mdash;" if not v else f"{v[0]}-{v[1]}" + (f"-{v[2]}" if v[2] else "")

    def _wk_cell(picks):
        """This week's picks, folded away, agreement marked in the grade colour."""
        if not picks:
            return '<td class="pick">&mdash;</td>'
        lines, agree = [], 0
        for p_ in picks:
            g_ = agree_grade(p_)
            if g_:
                agree += 1
            cls = f' class="xp x{g_.lower()}"' if g_ else ' class="xp"'
            ttl = f' title="The card is on this side too, graded {g_}"' if g_ else ''
            lines.append(f'<div{cls}{ttl}><span class="xpg">{esc(p_["game"])}</span> '
                         f'{esc(p_["text"])}</div>')
        summ = f'{len(picks)} pick{"s" if len(picks) != 1 else ""}'
        if agree:
            summ += f', {agree} with us'
        return ('<td class="pick"><details class="xpd"><summary>' + summ
                + '</summary>' + "".join(lines) + '</details></td>')
    body = []
    for _, nm, sp, to, su, w, l, p in sorted(rows, reverse=True, key=lambda z: z[0]):
        n = w + l
        pct = f"{100 * w / n:.1f}%" if n else "&mdash;"
        if not n:
            read = "no settled picks yet"
        elif n < 10:
            read = f"{n} settled, too few to read"
        else:
            lo, hi = PICKS.wilson(w, l) if hasattr(PICKS, "wilson") else (0.0, 100.0)
            be = PICKS.BREAK_EVEN
            read = ("trending favorable, and the interval clears break-even" if lo > be
                    else "below break-even, and the interval says so" if hi < be
                    else "trending favorable, not yet distinguishable from luck"
                    if 100 * w / n > be else "at or below break-even")
        wk = EXPERT_WEEK.get(nm) or []
        body.append(f'<tr><td>{esc(nm)}</td>' + _wk_cell(wk)
                    + f'<td class="num">{cell(sp)}</td>'
                    f'<td class="num">{cell(to)}</td><td class="num">{cell(su)}</td>'
                    f'<td class="num">{cell([w, l, p])} ({pct})</td><td>{read}</td></tr>')
    return (            f'<div class="card">Every expert pick attached to this card with a market, side '
            f'and line is recorded before kickoff and settled from the final score. Spread and '
            f'total picks are graded at the line the expert took. The read weighs the two '
            f'against the {PICKS.BREAK_EVEN:.1f}% break-even and says nothing until an expert '
            f'has ten settled. Straight-up picks are counted but never read, because a win at '
            f'an unknown price says nothing about value.</div>'
            '<div class="scroll"><table class="sheet"><thead><tr><th>Expert</th>'
            '<th>This week</th><th>ATS</th>'
            '<th>Totals</th><th>Straight up</th><th>ATS + totals</th><th>Read</th>'
            '</tr></thead><tbody>' + "".join(body) + '</tbody></table></div>')


def results_rows():
    """Every pick of the season as one row set, for the Results tab.

    picks.csv is append-only and written before kickoff, and the nightly grade
    fills in win, loss or push, so this reads it and derives nothing. The same
    tab on the NFL card is built the same way from its own ledger files.
    """
    try:
        p = pd.read_csv(PICKS_PATH)
    except Exception:
        return []
    out = []
    for r in p.itertuples():
        res = str(getattr(r, "result", "") or "").strip().lower()
        res = {"win": "W", "loss": "L", "push": "P"}.get(res, "Open")
        side = str(getattr(r, "side", ""))
        mk = str(r.market).title()
        away, home = str(r.away), str(r.home)
        if mk == "Total":
            venue = ""
        else:
            venue = "Home" if side == home else ("Road" if side == away else "")
        out.append(dict(wk=int(r.week), away=away, home=home,
                        game=f"{away} at {home}", market=mk, side=side,
                        num=("" if pd.isna(r.number) else float(r.number)),
                        grade=str(r.grade), tier=str(r.tier), strategy=str(r.strategy),
                        res=res, venue=venue))
    return out


def results_tab():
    """The Results view: season to date, sliced every way the filters allow."""
    rows = results_rows()
    settled = [x for x in rows if x["res"] in ("W", "L", "P")]
    wks = sorted({x["wk"] for x in rows})
    mks = sorted({x["market"] for x in rows})
    trs = [t for t in ["PLAY", "LEAN", "PASS", "AVOID"] if any(x["tier"] == t for x in rows)]
    h = [f'<div class="card">Every pick this season, {len(settled):,} of {len(rows):,} settled '
         f'from final scores. Every table below reacts to the filters, including the export. '
         f'A record is only evidence when its 95% interval clears {PICKS.BREAK_EVEN:.1f}%, the '
         f'break-even of standard pricing, so each one carries its interval. Totals appear '
         f'under both teams, so team rows add up to more than the slate.</div>']
    h.append('<details class="fpanel" open><summary>Filters</summary><div class="filters">')

    def grp(label, cls, vals):
        """One filter group, as a dropdown with real checkboxes inside it."""
        h.append(f'<details class="fdrop"><summary><b>{label}</b>'
                 f'<span class="fsum">all</span></summary><div class="fpop">')
        for v in vals:
            h.append(f'<label><input type="checkbox" class="{cls}" value="{v}" checked '
                     f'onchange="lflt()">{v}</label>')
        h.append('</div></details>')
    grp("Market", "lmk", mks)
    grp("Grade", "lt", ["A", "B", "C", "D"])
    grp("Result", "lr", ["W", "L", "P", "Open"])
    grp("Tier", "ltr", trs)
    grp("Week", "lw", wks)
    grp("Venue", "lvn", ["Home", "Road"])
    h.append('<div class="fg"><b>Team</b><input id="lteam" type="search" placeholder="type a team" '
             'oninput="lflt()" style="padding:4px 6px"></div>')
    h.append('<div class="fg"><b>&nbsp;</b><button onclick="lAll(1)">Select all</button> '
             '<button onclick="lAll(0)">Clear</button> '
             '<button onclick="lcsv()">Download CSV</button>'
             '<div id="lcount" class="none" style="margin-top:6px"></div></div>')
    h.append('</div></details>')
    for sec, title in [("lsum", "Overall"), ("lgrade", "By grade"), ("lmkt", "By market"),
                       ("ltier", "By strategy tier"), ("lweek", "By week"),
                       ("lgrid", "Team by market")]:
        h.append(f'<h3 id="{sec}h">{title}</h3><div id="{sec}" class="scroll"></div>')
    h.append('<h3 id="s-picks">Every pick</h3><div id="lrows" class="scroll"></div>')
    return "\n".join(h)


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


def fbs_only(team, shown):
    """What to print where a measure exists for FBS and not for FCS.

    Talent is built from recruiting ratings, which barely cover FCS. SP+ is an
    FBS product. Returning production is published by CFBD for FBS only, and
    asking by classification and then conference by conference both came back
    empty. A bare dash reads as a gap we failed to fill; this says what it is.
    """
    if DIV_OF.get(str(team), "") == "fcs":
        return '<span class="none" title="This measure exists for FBS only">' \
               'no FCS equivalent</span>'
    return shown


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


def _offv(team, col):
    """One official number for a team, or None when it has none."""
    if not len(OFFICIAL) or str(team) not in OFFICIAL.index:
        return None
    v = OFFICIAL.loc[str(team)].get(col)
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return None if v != v else v


def _off(team, col):
    """The same number as text: whole where it is whole, one decimal otherwise."""
    v = _offv(team, col)
    if v is None:
        return "&mdash;"
    if abs(v - round(v)) < 1e-9:
        return f"{int(round(v))}"
    return f"{v:.1f}"


def _offr(team, col):
    v = _offv(team, col)
    return "&mdash;" if v is None else f"#{int(v)}"


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
        _cmp_row(poll_label(a, h), poll_cell(a)[0], poll_cell(h)[0],
                 poll_cell(a)[1], poll_cell(h)[1], True),
        _cmp_row("Model rank", rk(RANK, a), rk(RANK, h),
                 _tv(a, "rank"), _tv(h, "rank"), True),
        _cmp_row("Rating", fmt1(_tv(a, "rating")), fmt1(_tv(h, "rating")),
                 _tv(a, "rating"), _tv(h, "rating")),
        _cmp_row("Talent prior",
                 fbs_only(a, fmt1(_tv(a, "talent_prior"))),
                 fbs_only(h, fmt1(_tv(h, "talent_prior"))),
                 _tv(a, "talent_prior"), _tv(h, "talent_prior")),
        _cmp_row("Form on top of it", fmt1(_tv(a, "form")), fmt1(_tv(h, "form")),
                 _tv(a, "form"), _tv(h, "form")),
        _cmp_row("Returning production",
                 fbs_only(a, "&mdash;" if _tv(a, "ret_percentPPA") is None
                          else f'{_tv(a, "ret_percentPPA"):.0%}'),
                 fbs_only(h, "&mdash;" if _tv(h, "ret_percentPPA") is None
                          else f'{_tv(h, "ret_percentPPA"):.0%}'),
                 _tv(a, "ret_percentPPA"), _tv(h, "ret_percentPPA")),
        _grp("OFFENSE"),
        # What has actually happened, from the official season-to-date yardage,
        # kept separate from the model's own view below it.
        _cmp_row("Yards / gm (official)", _off(a, "off_yds"), _off(h, "off_yds"),
                 _offv(a, "off_yds"), _offv(h, "off_yds")),
        _cmp_row("Rank, total offense", _offr(a, "off_yds_rank"), _offr(h, "off_yds_rank"),
                 _offv(a, "off_yds_rank"), _offv(h, "off_yds_rank"), True),
        _cmp_row("Rank, pass offense", _offr(a, "off_pass_rank"), _offr(h, "off_pass_rank"),
                 _offv(a, "off_pass_rank"), _offv(h, "off_pass_rank"), True),
        _cmp_row("Rank, rush offense", _offr(a, "off_rush_rank"), _offr(h, "off_rush_rank"),
                 _offv(a, "off_rush_rank"), _offv(h, "off_rush_rank"), True),
        _cmp_row("Giveaways / gm", _off(a, "give"), _off(h, "give"),
                 _offv(a, "give"), _offv(h, "give"), True),
        _cmp_row("Points model rank", rk(OFF_RANK, a), rk(OFF_RANK, h),
                 OFF_RANK.get(a), OFF_RANK.get(h), True),
        _cmp_row("Points expected", pts(OFF, a), pts(OFF, h),
                 (None if a not in OFF.index else float(OFF[a])),
                 (None if h not in OFF.index else float(OFF[h]))),
        _cmp_row("SP+ offense",
                 fbs_only(a, fmt1(_tv(a, "sp_offense.rating"))),
                 fbs_only(h, fmt1(_tv(h, "sp_offense.rating"))),
                 _tv(a, "sp_offense.rating"), _tv(h, "sp_offense.rating")),
        _grp("DEFENSE"),
        _cmp_row("Yards allowed / gm (official)", _off(a, "def_yds"), _off(h, "def_yds"),
                 _offv(a, "def_yds"), _offv(h, "def_yds"), True),
        _cmp_row("Rank, total defense", _offr(a, "def_yds_rank"), _offr(h, "def_yds_rank"),
                 _offv(a, "def_yds_rank"), _offv(h, "def_yds_rank"), True),
        _cmp_row("Rank, pass defense", _offr(a, "def_pass_rank"), _offr(h, "def_pass_rank"),
                 _offv(a, "def_pass_rank"), _offv(h, "def_pass_rank"), True),
        _cmp_row("Rank, rush defense", _offr(a, "def_rush_rank"), _offr(h, "def_rush_rank"),
                 _offv(a, "def_rush_rank"), _offv(h, "def_rush_rank"), True),
        _cmp_row("Takeaways / gm", _off(a, "take"), _off(h, "take"),
                 _offv(a, "take"), _offv(h, "take")),
        _cmp_row("Points model rank", rk(DEF_RANK, a), rk(DEF_RANK, h),
                 DEF_RANK.get(a), DEF_RANK.get(h), True),
        _cmp_row("Points allowed", pts(DEF, a), pts(DEF, h),
                 (None if a not in DEF.index else float(DEF[a])),
                 (None if h not in DEF.index else float(DEF[h])), True),
        # Lower is better in SP+ defense: it correlates -0.83 with team rating in
        # this file, Ohio State 8.4 against Massachusetts 41.2. Shaded the other
        # way it marked the worse defence as the better one on every card.
        _cmp_row("SP+ defense",
                 fbs_only(a, fmt1(_tv(a, "sp_defense.rating"))),
                 fbs_only(h, fmt1(_tv(h, "sp_defense.rating"))),
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
        f.append("cross-division")
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
                if not _expert_ok(e):
                    continue
                tracked = expert_short(e.get("name", ""))
                items.append(f'<b>{esc(str(e.get("name", "")))}</b> '
                             f'({esc(str(e.get("record", "record n/a")))}) &mdash; '
                             f'{esc(str(e.get("pick", "")))}'
                             + (f' <i>tracked here: {esc(tracked)}</i>' if tracked else ''))
            elif _expert_ok({"name": str(e)}):
                items.append(esc(str(e)))
        out.append(sec("Expert picks", items))
    # "log" is the structured news log, recorded to docs/newslog.csv rather than
    # rendered. Listing it here keeps it out of the catch-all panel.
    known = {"injuries", "returning", "trades", "transfers", "coaching", "suspensions",
             "movement", "birthdays", "notable", "experts", "log"}
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
        g = (MS.STATE.get("groups") or {}).get("cross") or {}
        if g:
            out.append(sec("How far to trust this one", [
                f'One side is FBS and the other FCS, the group the model understands least. '
                f'Over {g.get("games", 0):,} such games our number missed by '
                f'{g.get("our_mae", 0):.2f} points against the market\'s '
                f'{g.get("market_mae", 0):.2f}, a gap of '
                f'{g.get("our_mae", 0) - g.get("market_mae", 0):+.2f}, where the same gap on '
                f'FBS games is +0.62. And when we disagree with the opening number the close '
                f'moves toward us {g.get("clv_pct", 0):.1f}% of the time, which is a coin flip. '
                f'The grade here is worked out exactly as it is everywhere else; this is the '
                f'ground it stands on.']))
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

    # "row" is what the filters look for: without it the panels stayed put while
    # the summary table above them filtered, which is not what the NFL card does.
    return (f'<details class="gc row" data-day="{esc(day)}" data-gid="{esc(gid)}" '
            f'data-slate="{esc(slate_of(_t))}" data-div="{esc(str(r.get("div", "")))}">'
            f'<summary>'
            f'<span class="car">&rsaquo;</span>'
            f'<span><span class="gcH">{tm(r["away"])}'
            f'<span class="vs">at</span>{tm(r["home"])}</span>'
            f'<div class="gcM">{game_meta(r)}</div>'
            f'<div class="gcP">{preview_rows(r)}</div></span>'
            + (f'<div class="gcF">{head_tag}</div>' if r["final"]
               else game_flags(r, mk, pp))
            + '</summary><div class="body">'
            + "".join(body) + '</div></details>')


DIV_OF = {}
for _g in CUR.itertuples():
    for _t, _d in ((getattr(_g, "home_team", None), getattr(_g, "home_div", None)),
                   (getattr(_g, "away_team", None), getattr(_g, "away_div", None))):
        if _t and _d and str(_t) not in DIV_OF:
            DIV_OF[str(_t)] = str(_d).lower()


def load_official():
    """Season-to-date yardage and turnovers, and the ranks that follow.

    CFBD publishes each team's own totals AND its opponents' totals, so yards
    allowed needs no second call. Per game, because teams have played different
    numbers of games. This is what happened, not what the model thinks: the
    model's view is the Rating column, and the two are kept apart on purpose,
    exactly as Model # and the NFL.com ranks are kept apart on the NFL card.
    """
    f = P("season_stats.csv")
    if not os.path.exists(f):
        return pd.DataFrame()
    try:
        raw = pd.read_csv(f)
        w = raw.pivot_table(index="team", columns="stat", values="value", aggfunc="first")
    except Exception as e:
        ISSUES.append(("official stats",
                       f"season_stats.csv is present but unreadable ({e}), so the official "
                       "yardage ranks are missing from the cheat sheet."))
        return pd.DataFrame()
    need = ["games", "totalYards", "totalYardsOpponent", "netPassingYards",
            "netPassingYardsOpponent", "rushingYards", "rushingYardsOpponent",
            "turnovers", "turnoversOpponent"]
    if any(c not in w.columns for c in need):
        ISSUES.append(("official stats",
                       "CFBD returned season stats without the yardage columns the card "
                       "expects, so the official ranks are left off rather than half filled."))
        return pd.DataFrame()
    g = w["games"].replace(0, pd.NA)
    o = pd.DataFrame(index=w.index)
    o["games"] = w["games"]
    o["off_yds"] = w["totalYards"] / g
    o["def_yds"] = w["totalYardsOpponent"] / g
    o["off_pass"] = w["netPassingYards"] / g
    o["def_pass"] = w["netPassingYardsOpponent"] / g
    o["off_rush"] = w["rushingYards"] / g
    o["def_rush"] = w["rushingYardsOpponent"] / g
    o["give"] = w["turnovers"] / g
    o["take"] = w["turnoversOpponent"] / g
    o["to_diff"] = o["take"] - o["give"]
    # Rank inside the team's OWN division. FCS teams are in this file now, and
    # ranking Fordham's yards against FBS defences would be a number that looks
    # precise and means nothing. One ranking per division, same as the polls.
    o["div"] = pd.Series({t: DIV_OF.get(t, "") for t in o.index})
    for c, asc in (("off_yds", False), ("off_pass", False), ("off_rush", False),
                   ("def_yds", True), ("def_pass", True), ("def_rush", True)):
        o[c + "_rank"] = (o.groupby("div")[c].rank(ascending=asc, method="min")
                          .astype("Int64"))
    return o


_chrome = CHROME.drift_issue(str(MS.STATE.get("chrome_sha", "")))
if _chrome:
    ISSUES.append(_chrome)
print(f"shared chrome: v{CHROME.CHROME_VERSION} {CHROME.chrome_sha()}")

OFFICIAL = load_official()
print(f"official stats: {len(OFFICIAL)} teams")


def load_poll():
    """The most recent AP Top 25 on file, and which week it is.

    The AP poll is the college answer to NFL.com's weekly power rankings. It
    ranks 25 of 136 teams, so most rows are blank, and it lags: the new poll
    lands on Sunday, so during a week the latest one may be last week's. The
    card shows which week it is rather than implying it is current.
    """
    f = P("rankings.csv")
    if not os.path.exists(f):
        return {}, None
    try:
        r = pd.read_csv(f)
        out, weeks, names = {}, {}, {}
        # The AP poll is FBS only. FCS teams have their own, and showing an FCS
        # team as "unranked" against a poll it cannot appear in is wrong rather
        # than merely empty. Each division gets the poll that ranks it.
        for poll, div in (("AP Top 25", "fbs"), ("FCS Coaches Poll", "fcs")):
            p = r[r.poll.astype(str).str.strip().eq(poll)]
            if not len(p):
                continue
            wk = int(p.week.max())
            weeks[div], names[div] = wk, poll
            for t in p[p.week == wk].itertuples():
                out[str(t.team)] = (int(t.rank), div)
        if not out:
            return {}, {}, {}
        return out, weeks, names
    except Exception:
        return {}, {}, {}


POLL, POLL_WEEK, POLL_NAME = load_poll()
AP_WEEK = POLL_WEEK.get("fbs")
AP_RANK = {t: v[0] for t, v in POLL.items() if v[1] == "fbs"}
print(f"polls: {len(POLL)} ranked teams "
      + ", ".join(f"{POLL_NAME[d]} wk {POLL_WEEK[d]}" for d in POLL_WEEK))


def poll_cell(team):
    """How this team is ranked, in the poll that covers its own division."""
    got = POLL.get(str(team))
    if got:
        return f"#{got[0]}", got[0]
    d = DIV_OF.get(str(team), "")
    return ("unranked" if d in POLL_WEEK else "no poll"), None


def poll_label(a, h):
    divs = {DIV_OF.get(str(a), ""), DIV_OF.get(str(h), "")}
    if divs == {"fcs"} and "fcs" in POLL_NAME:
        wk = POLL_WEEK.get("fcs")
        return "FCS Coaches" + (f" (wk {wk})" if wk else "")
    if "fbs" in divs and "fcs" in divs:
        return "Poll"
    return f"AP Top 25{f' (wk {AP_WEEK})' if AP_WEEK else ''}"


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
            f'<td class="num">{num("ret_percentPPA", "{:.0%}")}</td>'
            + _official_cells(t.team) + '</tr>')
    extra = (f'<th>AP{f" wk {AP_WEEK}" if AP_WEEK else ""}</th><th>Off</th><th>Def</th><th>Pass off</th><th>Rush off</th>'
             '<th>Pass def</th><th>Rush def</th><th>Take/gm</th><th>Give/gm</th>'
             '<th>TO diff</th>') if len(OFFICIAL) or AP_RANK else ''
    return ('<div class="scroll"><table><thead><tr><th>Model #</th><th>Team</th><th>Conf</th>'
            '<th>Rating</th><th>Talent prior</th><th>Form</th><th>SP+</th>'
            '<th>Ret. prod.</th>' + extra + '</tr></thead><tbody>'
            + "".join(body) + '</tbody></table></div>')


def _official_cells(team):
    """The counted columns: AP rank, official yardage ranks, turnovers."""
    if not (len(OFFICIAL) or AP_RANK):
        return ''
    ap = AP_RANK.get(str(team))
    cells = [f'<td class="num">{"#" + str(ap) if ap else "&mdash;"}</td>']
    row = None
    if len(OFFICIAL) and str(team) in OFFICIAL.index:
        row = OFFICIAL.loc[str(team)]
    for c in ("off_yds_rank", "def_yds_rank", "off_pass_rank", "off_rush_rank",
              "def_pass_rank", "def_rush_rank"):
        v = None if row is None else row.get(c)
        cells.append(f'<td class="num">{"#" + str(int(v)) if v == v and v is not None else "&mdash;"}</td>')
    for c in ("take", "give", "to_diff"):
        v = None if row is None else row.get(c)
        if v is None or v != v:
            cells.append('<td class="num">&mdash;</td>')
        else:
            whole = abs(float(v) - round(float(v))) < 1e-9
            sign = "+" if c == "to_diff" else ""
            txt = f"{int(round(float(v))):+d}" if (whole and c == "to_diff") else (
                  f"{int(round(float(v)))}" if whole else f"{float(v):{sign}.1f}")
            cells.append(f'<td class="num">{txt}</td>')
    return "".join(cells)


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
<tr><td><b>blank</b></td><td>Nothing to say about this game: no pricing inconsistency, no
split between the markets, no model disagreement. The column is left empty rather than filled
with filler, so anything written in it is worth reading.</td></tr>
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
    "shared chrome": ("INFO", "The shared page code differs between the two cards",
                      "card_chrome.py is meant to be byte identical in the NFL and college "
                      "repositories. Copy the newer one across and update chrome_sha in both "
                      "model_state.json files."),
    "expert picks": ("INFO", "Something in the expert picks could not be used",
                     "Only named people with a market, side and line build a record. Fix it "
                     "at the next research run; the picks themselves are unaffected."),
    "official stats": ("WARN", "The official season-to-date stats are unusable",
                       "The cheat sheet falls back to the model's columns alone. The next "
                       "fetch rewrites the file; if it keeps happening the CFBD answer has "
                       "changed shape."),
    "archive weeks": ("WARN", "An earlier week's page could not be relinked",
                      "Its week dropdown still lists only the weeks that existed when it was "
                      "written, so it cannot navigate forward. The page itself is untouched: "
                      "nothing is rewritten unless the change can be proved to be the dropdown "
                      "and nothing else."),
    "missing game": ("WARN", "A scheduled game is not on the card",
                     "Refetch the schedule and rebuild. If it persists the team name is not matching between files."),
    "duplicate": ("ERROR", "The same game is rendered more than once",
                  "The dedupe on the games frame is not holding. Do not trust the counts on this page."),
    "stale data": ("WARN", "A fetched dataset is past its own refresh age",
                   "The fetch reuses data until it ages out. One or more datasets are older "
                   "than their own limit, so the refresh that should have replaced them is "
                   "not happening. Check the last run's log for a failed pull."),
    "no fetch log": ("WARN", "There is no record of when the data was fetched",
                     "scripts/data/fetched.json is missing, so no dataset can be checked for "
                     "being overdue and the next run refetches everything at full API cost. "
                     "It is written by fetch_data.py and committed with the rest of data/."),
    "no line": ("INFO", "Some games have no posted spread yet",
                "No action. Books post college numbers late in the week and the next refresh picks them up."),
    "unrated team": ("INFO", "A team on the card has no rating",
                     "No action. A team below the minimum games threshold, which resolves "
                     "as the season fills in. The game is still shown; what is missing is "
                     "the model number, not the game."),
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
    "no research": ("WARN", "No weekly research is attached to this card",
                    "Research the slate and commit scripts/notes.json. Injuries, coaching "
                    "and line movement are exactly what the market prices and the model "
                    "does not."),
    "research stale": ("ERROR", "The research file matches no game this season",
                       "notes.json is keyed AWAY@HOME. None of its keys are on the "
                       "schedule at all, so the team names are wrong."),
    "research week": ("INFO", "The research file is for a different week",
                      "No action if it is ahead of the card; it appears when the week "
                      "rolls forward. If it is behind, replace it."),
    "no second odds feed": ("INFO", "Only CFBD is supplying prices",
                            "The consensus still works, on fewer books. Check that ODDS_API_KEY "
                            "is set and that the last run was inside the freshness window."),
    "picks unattributed": ("INFO", "Some settled picks cannot be credited to a strategy",
                           "No action. Rows written before the moneyline strategies existed. Picks are append-only, so they stay as issued and are simply not counted."),
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
    "official stats": "cheat",
    "shared chrome": "all",
    "expert picks": "ledger",
    "missing game": "card", "duplicate": "card", "no line": "card",
    "unrated team": "card", "total out of range": "card", "empty card": "card",
    "placeholder moneylines": "card", "no weather": "card", "no venues": "card",
    "gap looks wrong": "card",
    "odds names": "card", "odds unmatched": "card", "no second odds feed": "card",
    "no research": "card", "research stale": "card", "research week": "card",
    "stale data": "all", "no fetch log": "all",
    "odds in play": "card",
    "count mismatch": "cheat",
    "duplicate picks": "ledger", "picks cleaned": "ledger",
    "picks unattributed": "ledger",
    "state file": "all", "backtest date": "all",
}


# An INFO line whose fix begins "No action" is not asking for anything: it says
# the card already handled it. Those belong in the run log, not in a panel the
# reader is meant to act on. Same rule as the NFL card, same wording.
_NOACTION = ("no action", "nothing to do", "resolves automatically",
             "resolves itself", "no action needed")


def worth_attention(kind):
    """False when this kind is INFO and its own fix says nothing need be done."""
    lvl, _title, fix = FIXES.get(kind, ("WARN", kind.title(), "No fix recorded."))
    return not (lvl == "INFO" and any(p in str(fix).lower() for p in _NOACTION))


def issues_html():
    global ISSUES
    _skipped = [k for k, _ in ISSUES if not worth_attention(k)]
    for k in dict.fromkeys(_skipped):
        print(f"  [skipped, no action] {FIXES.get(k, ('', k, ''))[1]}")
    ISSUES = [(k, m) for k, m in ISSUES if worth_attention(k)]
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
def archived_weeks():
    weeks = set()
    try:
        for f in os.listdir(DOCS):
            m = re.fullmatch(r"week(\d+)\.html", f)
            if m:
                weeks.add(int(m.group(1)))
    except OSError:
        pass
    weeks.add(int(WEEK))
    return sorted(weeks)


def week_options(on_week=None):
    """The week dropdown, as seen from the page for on_week.

    on_week is which page these options are being written into, NOT which week
    is current. They differ on an archived page: week1.html has to show Week 1
    as the one you are looking at while still offering Week 2 as the current
    one. Written from the current week's point of view only, every archive
    would be a dead end that could not navigate forward, which is the whole
    reason this takes an argument.
    """
    on_week = int(WEEK) if on_week is None else int(on_week)
    out = []
    for w in archived_weeks():
        cur = (w == int(WEEK))
        # the current week is always index.html, so a bookmark of the root keeps working
        href = "index.html" if cur else f"week{w}.html"
        out.append(f'<option value="{href}"{" selected" if w == on_week else ""}>'
                   f'Week {w}{" (current)" if cur else ""}</option>')
    return "".join(out)


WK_SELECT_RE = re.compile(r'(<select id="wk"[^>]*>)(.*?)(</select>)', re.S)


def refresh_archive_weeks():
    """Put the full week list into every archive that was written earlier.

    An archive is frozen the moment its week rolls over, so its dropdown lists
    only the weeks that existed then. Week 1's page would offer Week 1 and
    nothing else for the rest of the season. This rewrites JUST the option list
    inside each archive and leaves every other byte alone.

    The invariant is checked, not assumed: swapping the new block back for the
    old one has to reproduce the original file exactly. Anything that does not
    match exactly once is skipped and reported rather than written over. See
    11.7 and 10.2 for why a silent partial write is the thing to be afraid of.
    """
    done, skipped = [], []
    for w in archived_weeks():
        if w == int(WEEK):
            continue                    # rewritten in full by this run anyway
        path = os.path.join(DOCS, f"week{w}.html")
        try:
            before = open(path, encoding="utf-8").read()
        except OSError as e:
            skipped.append((w, f"could not be read ({e})")); continue
        hits = WK_SELECT_RE.findall(before)
        if len(hits) != 1:
            skipped.append((w, f"{len(hits)} week dropdowns found, expected 1")); continue
        opts = week_options(on_week=w)
        after = WK_SELECT_RE.sub(lambda m: m.group(1) + opts + m.group(3), before, count=1)
        if after == before:
            continue                    # already current, nothing to write
        old_block = hits[0][1]
        if after.replace(opts, old_block, 1) != before:
            skipped.append((w, "rewrite changed more than the dropdown")); continue
        with open(path, "w", encoding="utf-8") as f:
            f.write(after)
        done.append(w)
    return done, skipped


_relinked, _relink_skipped = refresh_archive_weeks()
if _relinked:
    print(f"relinked the week dropdown in {len(_relinked)} earlier page(s): "
          + ", ".join(f"week{w}" for w in _relinked))
for _w, _why in _relink_skipped:
    ISSUES.append(("archive weeks", f"docs/week{_w}.html was left alone: {_why}"))

WEEKOPTS = week_options()

SEASON_TXT = f"{int(CUR.season.max()) if 'season' in CUR.columns and len(CUR) else ''} season".strip()
in_scope = [r for r in rows if not r["final"]]
cross_rows = []
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
/* A grade is a shade, not a coloured word. One small palette of four tints
   carries every grade on the page, and team colour is left to team names. */
.gA, .gB, .gC, .gD {{ display:inline-block; padding:1px 6px; border-radius:4px;
line-height:1.5; }}
.gA {{ background:var(--abg); color:var(--a); }}
.gB {{ background:var(--bbg); color:var(--b); }}
.gC {{ background:var(--cbg); color:var(--c); }}
.gD {{ background:var(--dbg); color:var(--d); }}
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
/* The side we would take carries the same shade as its grade, so the two read
   as one statement instead of two colours. The team name inside keeps its own
   colour: .tm-* sets colour on the inner span and wins over the chip's, and
   every team colour is chosen to clear 4.5:1 against all four of these shades.
   The colour on the chip itself is the fallback for a pick with no team in it,
   such as OVER. */
.pk-a, .pk-b, .pk-c, .pk-d {{ display:inline-block; padding:1px 6px;
border-radius:4px; font-weight:700; line-height:1.5; }}
.pk-a, .pk-b, .pk-c, .pk-d {{ color:var(--ink); border-left:3px solid var(--pkc);
  background:color-mix(in srgb, var(--pkc) 13%, var(--pan)); }}
.pk-a {{ --pkc:var(--a); }} .pk-b {{ --pkc:var(--b); }}
.pk-c {{ --pkc:var(--c); }} .pk-d {{ --pkc:var(--d); }}
.none {{ color:var(--mute); font-size:13px; font-style:italic; }}
.card.chg{{border-left:3px solid var(--b)}}
.chgA{{color:var(--a);font-weight:700}}
.chgR{{color:#b3313c;font-weight:700}}
.chgGist{{color:var(--mute);font-size:12px;margin-left:8px}}
.lbl{{font-size:11px;text-transform:uppercase;letter-spacing:.07em;color:var(--mute);margin:8px 0 3px}}
ul.nl{{margin:0 0 4px 18px;padding:0;font-size:13px}}
.secnav{{display:flex;flex-wrap:wrap;gap:7px;margin:-4px 0 12px}}
.secnav a{{font-size:11.5px;color:var(--mute);border:1px solid var(--line);border-radius:20px;
 padding:2px 9px;cursor:pointer;text-decoration:none}}
""" + CHROME.dropdown_css() + f"""
details#help > summary {{ cursor:pointer; list-style:none; font-size:13px; text-transform:uppercase;
 letter-spacing:.09em; color:var(--mute); margin:26px 0 10px; font-weight:600; }}
details#help > summary::-webkit-details-marker {{ display:none; }}
details#help > summary::after {{ content:" \u25be"; }}
details#help[open] > summary::after {{ content:" \u25b4"; }}
details.xpd > summary {{ cursor:pointer; list-style:none; font-size:12px; color:var(--mute); }}
details.xpd > summary::-webkit-details-marker {{ display:none; }}
details.xpd > summary::after {{ content:" \u25be"; }}
details.xpd[open] > summary::after {{ content:" \u25b4"; }}
.xp {{ padding:2px 0 2px 8px; border-left:3px solid transparent; margin-top:3px;
 font-size:12.5px; white-space:nowrap; }}
.xp .xpg {{ color:var(--mute); margin-right:5px; }}
.xp.xa {{ border-left-color:var(--a); }} .xp.xb {{ border-left-color:var(--b); }}
.xp.xc {{ border-left-color:var(--c); }} .xp.xd {{ border-left-color:var(--d); }}
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

<h2 id="attn">Needs attention</h2>
{issues_html()}

<div id="v-card">
<h2 id="summary">Summary &mdash; all markets</h2>
<div class="secnav" data-own="summary"></div>
{summary_table()}


<h2 id="changes">What changed since the last update</h2>
<div class="secnav" data-own="changes"></div>
{changes_html()}


<h2 id="notes">Game notes</h2>
<div class="secnav" data-own="notes"></div>
<div style="margin:-2px 0 10px"><button onclick="expAll(1)">Expand all</button>
<button onclick="expAll(0)">Collapse all</button></div>
{"".join(game_card(r) for r in in_scope) or '<p class="muted">No in-scope games left to play this week.</p>'}
{('<h3>Already played this week</h3>' + "".join(game_card(r) for r in final_rows)) if final_rows else ''}
{('<h3>Cross-division, for reference</h3>' + "".join(game_card(r) for r in cross_rows)) if cross_rows else ''}

<h2 id="experts">Expert records, tracked here</h2>
<div class="secnav" data-own="experts"></div>
{expert_table()}

</div><!-- /v-card -->

<div id="v-cheat">
<h2 id="sheet">Team cheat sheet</h2>
<div class="secnav" data-own="sheet"></div>
<p class="muted">Rating is points against an average FBS team on a neutral field. Talent
prior is where recruiting alone would put a team, form is what results have said on top.
SP+ runs alongside as a cross-check and is kept out of the ratings.</p>
{cheat_sheet()}

<h2 id="conf">Rankings by conference</h2>
<div class="secnav" data-own="conf"></div>
<p class="muted">The same ratings, one block per conference. FBS first.</p>
{rankings_by_conference()}

</div><!-- /v-cheat -->

<div id="v-ledger">
<h2 id="results">Results, season to date</h2>
<div class="secnav" data-own="results"></div>
{results_tab()}
{clv_block()}

<h2 id="ledger">This week's picks</h2>
{picks_ledger()}
<h3>How our number compares with the market's</h3>
{accuracy_ledger()}

</div><!-- /v-ledger -->

<div class="nav" id="pagenav" style="position:static;margin-top:26px;border-bottom:none"></div>
<details id="help"><summary>How to read</summary>
<h3 id="strategies">Where each strategy stands</h3>
{strategy_table()}
{how_to_read()}
</details>

<footer>
Ratings: opponent-adjusted ridge on game margins, shrunk toward a talent prior.
Home field {HFA:+.1f}. FBS over FCS {META.get('fcs_gap', 0):+.1f}. Built from
{META.get('games_used', 0):,} games across {META.get('teams', 0)} teams.
Picks are append-only and keep the number they were issued at.
No bet sizing or staking advice appears here by design.
</footer>

</div>
<script>
var LROWS = {json.dumps(results_rows())};
var LBE = {PICKS.BREAK_EVEN};
// Day and game filters over the summary table. An empty group hides everything;
// a fully ticked group imposes no constraint. Same rule as the NFL card.
function flt(){{
 var gAll=document.querySelectorAll('.fgm').length;
 var FILTER_GROUPS=[{{cls:'fd',attr:'day'}},{{cls:'fsl',attr:'slate'}},
                    {{cls:'fdv',attr:'div'}},{{cls:'fgm',attr:'gid'}}];
 // One rule for every group, shared with the NFL card in card_chrome.py: a
 // group that is empty or fully ticked constrains nothing, active groups
 // combine as an AND, and clearing everything shows nothing.
 [].slice.call(document.querySelectorAll('.row')).forEach(function(rw){{
   rw.style.display = rowVisible(rw, FILTER_GROUPS) ? '' : 'none';}});
 var n=0;
 [].slice.call(document.querySelectorAll('.row')).forEach(function(rw){{
   if(rw.style.display!=='none') n++;}});
 var c=document.getElementById('fcount');
 if(c) c.textContent=n+' of '+gAll+' games shown';
 if(typeof fdrops==='function') fdrops();}}
// ---- the three views, and the nav strip that changes with them ----
var NAVS={{
 card:[['attn','Needs attention'],['summary','Summary'],['changes','What changed'],
       ['notes','Game notes'],['experts','Expert records'],['help','How to read']],
 cheat:[['sheet','Team cheat sheet'],['conf','Rankings by conference'],['help','How to read']],
 ledger:[['results','Results'],['clv','Closing line value'],['s-picks','Every pick'],
         ['ledger',"This week"],['help','How to read']]}};
function mkLink(p){{
 var t=document.getElementById(p[0]); if(!t) return null;
 var a=document.createElement('a'); a.href='#'+p[0]; a.textContent=p[1];
 a.onclick=function(e){{e.preventDefault(); t.scrollIntoView({{behavior:'smooth',block:'start'}});}};
 return a;}}
function pagenav(v){{
 var pn=document.getElementById('pagenav'); if(!pn) return;
 pn.innerHTML='';
 var lbl=document.createElement('span'); lbl.textContent='Other pages:';
 lbl.style.cssText='font-size:12px;color:var(--mute);align-self:center'; pn.appendChild(lbl);
 var PG={{card:'Weekly Card',cheat:'Team Cheat Sheet',ledger:'Results'}};
 Object.keys(NAVS).forEach(function(k){{ if(k===v) return;
   NAVS[k].forEach(function(p){{ if(p[0]==='help') return;
     if(!document.getElementById(p[0])) return;
     var a=document.createElement('a'); a.href='#'+p[0];
     a.textContent=PG[k]+' \u00b7 '+p[1];
     a.onclick=function(e){{e.preventDefault();
       document.getElementById('view').value=k; setView();
       document.getElementById(p[0]).scrollIntoView({{behavior:'smooth',block:'start'}});}};
     pn.appendChild(a);}});}});}}
function setView(){{
 var v=document.getElementById('view').value;
 ['card','cheat','ledger'].forEach(function(k){{
   var el=document.getElementById('v-'+k); if(el) el.classList.toggle('hide', v!==k);}});
 var n=document.getElementById('nav');
 if(n){{n.innerHTML=''; (NAVS[v]||[]).forEach(function(p){{var a=mkLink(p); if(a) n.appendChild(a);}});}}
 // per-section strips: every other section on this page, never its own
 [].slice.call(document.querySelectorAll('.secnav')).forEach(function(el){{
   el.innerHTML='';
   var own=el.dataset.own;
   (NAVS[v]||[]).forEach(function(p){{ if(p[0]===own||p[0]==='attn') return;
     var a=mkLink(p); if(a) el.appendChild(a); }});}});
 pagenav(v);
 // an issue belongs to a view; "all" is about the page itself and always shows
 var any=false;
 [].slice.call(document.querySelectorAll('.iss')).forEach(function(el){{
   var t=el.dataset.view||'card', on=(t==='all'||t===v);
   el.style.display=on?'':'none'; if(on) any=true;}});
 var hdr=document.getElementById('attn');
 if(hdr) hdr.classList.toggle('hide', !any);
 try{{localStorage.setItem('cfbview', v);}}catch(e){{}}
}}
""" + CHROME.stats_js("good", "bad", "&mdash;") + CHROME.sort_js() + CHROME.dropdown_js() + CHROME.rowfilter_js() + f"""
function lmatch(){{
 var g={{lmk:'market',lt:'grade',lr:'res',ltr:'tier',lw:'wk',lvn:'venue'}}, sel={{}}, all={{}};
 Object.keys(g).forEach(function(c){{ sel[c]=lsel(c); all[c]=document.querySelectorAll('.'+c).length; }});
 var q=(document.getElementById('lteam')||{{}}).value||'';
 q=q.trim().toLowerCase();
 return LROWS.filter(function(r){{
   for(var c in g){{ if(sel[c].length===0) return false;
     if(sel[c].length!==all[c] && sel[c].indexOf(String(r[g[c]]))<0) return false; }}
   if(q && r.away.toLowerCase().indexOf(q)<0 && r.home.toLowerCase().indexOf(q)<0) return false;
   return true;}});}}
var LCUR=[];
function lflt(){{
 if(!document.getElementById('lsum')) return;
 var R=lmatch(); LCUR=R; var t=tally(R);
 document.getElementById('lsum').innerHTML = tbl('<th>All picks</th>'+RH(),
   recRow('Season to date',R) + (t.o? '<tr><td>Still open</td><td colspan="4" class="num">'+t.o+' pick(s) not settled</td></tr>':''));
 var gh='';
 ['A','B','C','D'].forEach(function(x){{ var rs=R.filter(function(r){{return r.grade===x}});
   if(rs.length) gh+=recRow('<span class="g g'+x.toLowerCase()+'">'+x+'</span>',rs);}});
 document.getElementById('lgrade').innerHTML=tbl('<th>Grade</th>'+RH(), gh||'<tr><td>No picks</td></tr>');
 var mh='', mk=[...new Set(LROWS.map(function(r){{return r.market}}))].sort();
 mk.forEach(function(m){{ var rs=R.filter(function(r){{return r.market===m}});
   if(rs.length) mh+=recRow(m,rs);}});
 document.getElementById('lmkt').innerHTML=tbl('<th>Market</th>'+RH(), mh||'<tr><td>No picks</td></tr>');
 var th='';
 ['PLAY','LEAN','PASS','AVOID'].forEach(function(x){{ var rs=R.filter(function(r){{return r.tier===x}});
   if(rs.length) th+=recRow(x,rs);}});
 document.getElementById('ltier').innerHTML=tbl('<th>Tier</th>'+RH(), th||'<tr><td>No picks</td></tr>');
 var wh='', wk=[...new Set(R.map(function(r){{return r.wk}}))].sort(function(a,b){{return a-b}});
 wk.forEach(function(w){{ wh+=recRow('Week '+w, R.filter(function(r){{return r.wk===w}}));}});
 document.getElementById('lweek').innerHTML=tbl('<th>Week</th>'+RH(), wh||'<tr><td>No picks</td></tr>');
 var tm={{}};
 R.forEach(function(r){{ [r.away,r.home].forEach(function(x){{ (tm[x]=tm[x]||[]).push(r); }}); }});
 var names=Object.keys(tm).sort(function(a,b){{
   var f=function(x){{var t=tally(tm[x]);return t.w-t.l}}; return f(b)-f(a) || a.localeCompare(b);}});
 var gh2='';
 names.slice(0,200).forEach(function(x){{
   var cells='';
   mk.forEach(function(m){{ var z=tally(tm[x].filter(function(r){{return r.market===m}}));
     cells+='<td class="num">'+(z.w+z.l+z.p ? z.w+'-'+z.l+(z.p?'-'+z.p:'') : '&mdash;')+'</td>';}});
   var a=tally(tm[x]);
   gh2+='<tr><td>'+x+'</td>'+cells+recCell(a.w,a.l,a.p)+'<td class="num">'+(a.w+a.l+a.p)+'</td></tr>';}});
 document.getElementById('lgrid').innerHTML=tbl('<th>Team</th>'+mk.map(function(m){{return '<th>'+m+'</th>'}}).join('')+RH(), gh2||'<tr><td>No picks</td></tr>');
 var rh='';
 R.slice().sort(function(a,b){{return b.wk-a.wk || a.game.localeCompare(b.game) || a.market.localeCompare(b.market);}})
  .slice(0,1500).forEach(function(r){{
   rh+='<tr><td class="num">'+r.wk+'</td><td>'+r.game+'</td><td>'+r.market+'</td><td>'+r.side+'</td>'
     +'<td class="num">'+(r.num===''?'&mdash;':r.num)+'</td><td>'+r.tier+'</td>'
     +'<td><span class="g g'+String(r.grade).toLowerCase()+'">'+r.grade+'</span></td>'
     +'<td>'+(r.res==='Open'?'&mdash;':r.res)+'</td></tr>';}});
 document.getElementById('lrows').innerHTML=tbl(
   '<th>Wk</th><th>Game</th><th>Market</th><th>Side</th><th>Number</th><th>Tier</th><th>Grade</th><th>Result</th>',
   rh||'<tr><td>No picks match these filters</td></tr>');
 fdrops();
 makeSortable(document.getElementById('v-ledger'));
 makeSortable(document.getElementById('v-cheat'));
 var c=document.getElementById('lcount');
 if(c) c.textContent=R.length+' of '+LROWS.length+' picks shown, '+(t.w+t.l+t.p)+' settled';}}
function lAll(o){{[].slice.call(document.querySelectorAll('.lmk,.lt,.lr,.ltr,.lw,.lvn')).forEach(function(e){{e.checked=!!o}});
 var q=document.getElementById('lteam'); if(q&&!o) q.value=''; lflt();}}
function lcsv(){{
 csvDownload('cfb-card-results.csv',
   ['wk','game','market','side','num','tier','grade','res'], LCUR);}}
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
setView(); lflt();

function allOn(){{[].slice.call(document.querySelectorAll('.fd,.fgm,.fsl,.fdv')).forEach(function(e){{e.checked=true}});flt();}}
function allOff(){{[].slice.call(document.querySelectorAll('.fd,.fgm,.fsl,.fdv')).forEach(function(e){{e.checked=false}});flt();}}
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
# A doubled brace in the style or script block means an f-string was closed or
# opened in the wrong place and the browser code never rendered. A healthy page
# has none: "}}" does occur legitimately where a block and a function end
# together, "{{" does not. This shipped once here, breaking every filter and
# table on the page while the run reported success.
_code = "".join(re.findall(r"<style>.*?</style>|<script>.*?</script>", HTML, re.S))
if "{{" in _code:
    bad.append("the page's own code contains a doubled brace, so part of it was "
               "never rendered and the page is broken")
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
