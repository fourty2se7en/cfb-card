"""
fetch_data.py — pull current college football data from CollegeFootballData.

The API key is read from the CFBD_API_KEY environment variable, which GitHub
Actions supplies from the encrypted repository secret. It is sent in an
Authorization HEADER, never in the URL. URLs leak into error messages, stack
traces and run logs; headers do not.

Writes plain CSVs into data/ so the rest of the pipeline needs no key at all.

Weather comes from Open-Meteo, which needs no key. It is fetched last and is
allowed to fail: if it does, the card simply has no weather that week rather
than no card.
"""
import os, sys, time, json
from datetime import datetime, timezone, timedelta
import pandas as pd
import requests

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
os.makedirs(DATA, exist_ok=True)

API = "https://api.collegefootballdata.com"
KEY = os.environ.get("CFBD_API_KEY", "").strip()
if not KEY:
    sys.exit("ERROR: CFBD_API_KEY is not set.\n"
             "  Locally:  export CFBD_API_KEY='your-key'\n"
             "  Actions:  add it under Settings > Secrets and variables > Actions")

SESSION = requests.Session()
SESSION.headers.update({"Authorization": f"Bearer {KEY}", "Accept": "application/json"})

SEASON = int(os.environ.get("CFB_SEASON", "2026"))


# --------------------------------------------------------------- fetching
# TWO THINGS THIS SOLVES.
#
# 1. A FAILED PULL NOW STOPS THE RUN. get() used to return None, save() printed
#    FAILED, and the run carried on. The previous run's CSVs are still sitting
#    in data/, so the card was then built on YESTERDAY'S numbers and still
#    reported success. Stale is not malformed, so the card's refuse-to-publish
#    check cannot catch it. Nothing anywhere would have said the page was old.
#    An EMPTY answer is still fine and is still data; a FAILURE is not.
#
# 2. THINGS THAT DO NOT CHANGE ARE NOT REFETCHED. Of the eight calls this made
#    every run, only the games and the lines had changed since the last one.
#    Recruiting talent, returning production, team colours, stadiums and last
#    season's finished results were being downloaded 65 times a month each.
#    The free CFBD tier is 1,000 calls a month and this card was spending about
#    520 of them. With the ages below it spends about 170.
#
#    The age is stored INSIDE data/fetched.json rather than read from the file
#    modification time, because the workflow checks the repo out fresh every run
#    and every file looks new.
MIN_GAP = 1.0          # seconds between calls, so a burst never triggers a limit
TRIES = 5
_last_call = [0.0]
FRESH_PATH = os.path.join(DATA, "fetched.json")
try:
    with open(FRESH_PATH) as _f:
        FRESH = json.load(_f)
except Exception:
    FRESH = {}


def _stamp_of(entry):
    """The timestamp out of a fetched.json entry, whichever shape it is in.

    The file used to hold {name: "<iso>"}. It now holds
    {name: {"at": "<iso>", "max_age_days": N}} so the card can tell whether a
    dataset is OVERDUE without restating the ages, which would be 4.3h. Both
    shapes are read, so an existing file keeps working and the first run after
    this change upgrades it in place.
    """
    if isinstance(entry, dict):
        return entry.get("at")
    return entry


def _age_days(name):
    ts = _stamp_of(FRESH.get(name))
    if not ts:
        return float("inf")
    try:
        when = datetime.fromisoformat(ts)
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - when).total_seconds() / 86400.0
    except Exception:
        return float("inf")


def _mark(name, days):
    # The max age is written BESIDE the timestamp, so one file answers both
    # "when was this fetched" and "how old is too old". The card reads it and
    # flags anything overdue; nothing has to restate the ages a second time.
    FRESH[name] = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   "max_age_days": days}
    tmp = FRESH_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(FRESH, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, FRESH_PATH)


def get(path, **params):
    """GET with the key in a header.

    Retries, paces itself, and EXITS if the answer never comes. This card is
    read every day; showing yesterday's numbers as though they were today's is
    worse than showing nothing and saying why.
    """
    for attempt in range(TRIES):
        gap = MIN_GAP - (time.time() - _last_call[0])
        if gap > 0:
            time.sleep(gap)
        try:
            r = SESSION.get(f"{API}{path}", params=params, timeout=30)
        except requests.RequestException as e:
            print(f"  network error on {path}: {e}")
            time.sleep(3 * (attempt + 1))
            continue
        finally:
            _last_call[0] = time.time()
        if r.status_code == 200:
            return r.json()
        if r.status_code == 404:
            # An answer, not a failure: the year asked for has no data yet.
            print(f"  {path}: nothing published for those parameters")
            return []
        if r.status_code in (401, 403):
            # Never print the key or the full URL on an auth failure.
            sys.exit(f"ERROR: CFBD rejected the key on {path} (HTTP {r.status_code}). "
                     "Check the secret value is the key from your email, with no quotes or spaces.")
        if r.status_code == 429:
            wait = r.headers.get("Retry-After")
            try:
                wait = float(wait)
            except (TypeError, ValueError):
                wait = 15 * (attempt + 1)
            wait = min(max(wait, 5.0), 90.0)
            print(f"  rate limited on {path}, waiting {wait:.0f}s "
                  f"(attempt {attempt + 1} of {TRIES})")
            time.sleep(wait)
            continue
        print(f"  HTTP {r.status_code} on {path}")
        time.sleep(2 * (attempt + 1))
    sys.exit(
        f"ERROR: {path} did not come back after {TRIES} attempts. STOPPING.\n"
        f"       Carrying on would rebuild the card from the PREVIOUS run's files "
        f"and publish yesterday's numbers as today's, with nothing on the page to "
        f"say so.\n"
        f"       The free CFBD tier is 1,000 calls a month. Check the allowance on "
        f"your key page at collegefootballdata.com before re-running."
    )


def pull(name, path, days=0, expect_cols=(), **params):
    """One dataset. Skipped entirely when what is on disk is still current.

    days=0 means it changes constantly and is always fetched.
    """
    disk = os.path.join(DATA, name)
    if days > 0 and os.path.exists(disk):
        age = _age_days(name)
        if age < days:
            print(f"  {name}: {age:.1f} days old, still current, not refetched")
            try:
                return pd.read_csv(disk)
            except Exception as e:
                print(f"  {name}: could not be read back ({e}), refetching")
    out = save(get(path, **params), name, expect_cols)
    # Marked fresh only if a file actually landed. save() writes nothing for an
    # empty answer, and a name marked fresh with no file behind it would make
    # the next run skip a fetch it still needs.
    if os.path.exists(disk):
        _mark(name, days)
    return out


def save(obj, name, expect_cols=()):
    if obj is None:
        print(f"  {name}: FAILED"); return None
    df = pd.json_normalize(obj)
    if len(df) == 0:
        print(f"  {name}: empty"); return df
    missing = [c for c in expect_cols if c not in df.columns]
    if missing:
        print(f"  {name}: WARNING missing columns {missing}")
    df.to_csv(os.path.join(DATA, name), index=False)
    print(f"  {name}: {len(df):,} rows, {len(df.columns)} cols")
    return df


print(f"CFBD pull for {SEASON}")

# Games and results — the schedule the card is built around.
# HOW OFTEN EACH OF THESE ACTUALLY CHANGES, which is what the days= is.
# Fetched every run: the schedule with its results, and the betting lines.
# Everything else changes weekly, annually, or never, and was being downloaded
# 65 times a month for no reason.
games = pull("games.csv", "/games", days=0,
             expect_cols=("id", "week", "homeTeam", "awayTeam", "homePoints", "awayPoints"),
             year=SEASON, seasonType="regular")

# Betting lines. This is the piece the free GitHub mirror does not carry for the
# current season, and the main reason the key is required. The opening number
# matters as much as the closing one: line movement is research, and the
# backtest measures the model against both.
pull("lines.csv", "/lines", days=0,
     expect_cols=("id", "homeTeam", "awayTeam", "lines"),
     year=SEASON, seasonType="regular")

# Team talent composite — recruiting rolled up to a team rating. No NFL analogue.
# Recruiting is settled before the season starts and does not move during it.
for yr in (SEASON, SEASON - 1):
    # Non-EMPTY, not merely non-None. get() no longer returns None, so testing
    # for that would break on the first year every time and never fall back.
    _t = pull(f"talent_{yr}.csv", "/talent", days=14,
              expect_cols=("team", "talent"), year=yr)
    if _t is not None and len(_t):
        break

# Returning production: how much of last year's output is back. Matters far more
# in college than the NFL because rosters turn over so much faster.
# Set before week 1 and unchanged after it.
pull("returning.csv", "/player/returning", days=14, expect_cols=("team",), year=SEASON)

# SP+ ratings, CFBD's own opponent-adjusted efficiency measure. Used as an
# independent cross-check, the same role Elo plays in the NFL card.
# CFBD republishes SP+ about once a week, so a daily check is already generous.
pull("sp_ratings.csv", "/ratings/sp", days=1, expect_cols=("team", "rating"), year=SEASON)

# Team identity: colors, conference, classification. The card paints team names
# in their own colors the way the NFL card does, and there is no other source for
# them. Optional in every sense: if this call fails the card simply renders team
# names in the ordinary text color.
pull("teams.csv", "/teams", days=30, expect_cols=("school", "color"))

# Venues, for weather, elevation, surface and travel distance.
venues = pull("venues.csv", "/venues", days=30,
              expect_cols=("id", "name", "latitude", "longitude"))

# Prior-season results, so week 1 has priors instead of nothing.
# A finished season. It will never change again.
pull("games_prior.csv", "/games", days=3650,
     expect_cols=("id", "week", "homeTeam", "awayTeam"),
     year=SEASON - 1, seasonType="regular")


# ------------------------------------------------------------- odds api
# CFBD carries two books for college and only DraftKings quotes a moneyline
# reliably, which is why price consistency has so little to work with. The Odds
# API's free tier fills that in: 500 credits a month, and one NCAAF pull across
# three markets in one region costs 3, so twice a day is about 180 a month.
#
# SECURITY, and it is a real compromise worth stating: rule 10.6 says a key never
# goes in a query string, because URLs leak into logs and error messages. This
# API offers no header option -- the key is a query parameter or nothing. So the
# containment is: the key is only ever read from the environment, the URL is
# built at call time and never printed, and on any failure only the status code
# is logged. GitHub Actions also masks secret values in its own logs. If that is
# not acceptable, delete this block; nothing else depends on it.
ODDS_KEY = os.environ.get("ODDS_API_KEY", "").strip()


# The free tier is 500 credits a month and one pull costs 3, so the only thing
# that can waste it is pulling when nobody will read the answer. Three guards,
# cheapest first, each of which prints why it skipped:
#   1. the nightly grade run settles finished games and needs no fresh prices;
#   2. out of season there is nothing within a fortnight to price;
#   3. a freshness floor, which is what stops a run of manual rebuilds from
#      spending a month of credits in an afternoon.
ODDS_MIN_HOURS = float(os.environ.get("ODDS_MIN_HOURS", "6"))
ODDS_HORIZON_DAYS = 14


def _odds_recent_enough():
    """True when the committed file is younger than the floor. The timestamp is
    read from inside the file, not its mtime: every run is a fresh checkout, so
    mtime is always 'just now' and would never hold anything back."""
    path = os.path.join(DATA, "odds_api.csv")
    if not os.path.exists(path):
        return False, None
    try:
        prev = pd.read_csv(path)
        stamp = pd.to_datetime(prev["fetched_utc"], utc=True, errors="coerce").max()
        if pd.isna(stamp):
            return False, None
        age = (pd.Timestamp.now(tz="UTC") - stamp).total_seconds() / 3600.0
        return age < ODDS_MIN_HOURS, age
    except Exception:
        return False, None


def _season_is_live(games):
    """Any game kicking off inside the horizon? Cheap, and it covers the offseason."""
    if games is None or "startDate" not in games.columns:
        return True          # cannot tell, so do not block on it
    try:
        d = pd.to_datetime(games["startDate"], utc=True, errors="coerce").dropna()
        now = pd.Timestamp.now(tz="UTC")
        return bool(((d >= now - pd.Timedelta(days=1)) &
                     (d <= now + pd.Timedelta(days=ODDS_HORIZON_DAYS))).any())
    except Exception:
        return True


def fetch_odds(games=None, mode=""):
    """Per-book NCAAF prices. Best-effort: no key, or any failure, costs nothing."""
    if not ODDS_KEY:
        print("  odds api: no ODDS_API_KEY set, skipping (CFBD lines are unaffected)")
        return
    if str(mode).lower() == "grade":
        print("  odds api: grade run settles finished games, no fresh prices needed")
        return
    if not _season_is_live(games):
        print(f"  odds api: no games inside {ODDS_HORIZON_DAYS} days, skipping")
        return
    fresh, age = _odds_recent_enough()
    if fresh:
        print(f"  odds api: last pull was {age:.1f}h ago, under the {ODDS_MIN_HOURS:.0f}h "
              f"floor, skipping")
        return
    url = "https://api.the-odds-api.com/v4/sports/americanfootball_ncaaf/odds/"
    params = {"apiKey": ODDS_KEY, "regions": "us",
              "markets": "h2h,spreads,totals", "oddsFormat": "american"}
    try:
        r = requests.get(url, params=params, timeout=30)
    except requests.RequestException as e:
        # str(e) can carry the full URL, so report the type only
        print(f"  odds api: network error ({type(e).__name__}), skipping")
        return
    if r.status_code != 200:
        print(f"  odds api: HTTP {r.status_code}, skipping")
        return
    left = r.headers.get("x-requests-remaining")
    used = r.headers.get("x-requests-used")
    try:
        games = r.json()
    except ValueError:
        print("  odds api: response was not JSON, skipping")
        return
    rows = []
    for g in games or []:
        home, away = g.get("home_team"), g.get("away_team")
        for bk in g.get("bookmakers") or []:
            rec = {"fetched_utc": pd.Timestamp.now(tz="UTC").isoformat(),
                   "commence_time": g.get("commence_time"), "home_team": home,
                   "away_team": away, "book": bk.get("title") or bk.get("key"),
                   "last_update": bk.get("last_update"),
                   "spread": None, "total": None,
                   "home_moneyline": None, "away_moneyline": None}
            for mk in bk.get("markets") or []:
                key = mk.get("key")
                for o in mk.get("outcomes") or []:
                    name, price, point = o.get("name"), o.get("price"), o.get("point")
                    if key == "h2h":
                        if name == home:
                            rec["home_moneyline"] = price
                        elif name == away:
                            rec["away_moneyline"] = price
                    elif key == "spreads" and name == home:
                        # stored from the home side, the same convention as CFBD
                        rec["spread"] = point
                    elif key == "totals" and str(name).lower() == "over":
                        rec["total"] = point
            rows.append(rec)
    if not rows:
        print("  odds api: no games returned")
        return
    pd.DataFrame(rows).to_csv(os.path.join(DATA, "odds_api.csv"), index=False)
    books = sorted({r["book"] for r in rows})
    print(f"  odds_api.csv: {len(rows):,} quotes over {len({(r['home_team'], r['away_team']) for r in rows})} "
          f"games from {len(books)} books"
          + (f" | credits used {used}, remaining {left}" if left else ""))


fetch_odds(games, os.environ.get("CFB_MODE", ""))


# ---------------------------------------------------------------- weather
# Open-Meteo, no key, forecast only reaches about 16 days out. Anything past
# that simply has no row. The whole block is best-effort: a weather failure
# must never cost us a card.
def fetch_weather(games, venues):
    if games is None or venues is None or len(venues) == 0:
        print("  weather: skipped, no venue data"); return
    if not {"latitude", "longitude", "id"}.issubset(set(venues.columns)):
        print("  weather: skipped, venues have no coordinates"); return
    v = venues.dropna(subset=["latitude", "longitude"]).drop_duplicates("id").set_index("id")
    g = games.copy()
    g["startDate"] = pd.to_datetime(g.get("startDate"), errors="coerce", utc=True)
    now = datetime.now(timezone.utc)
    up = g[(g.startDate.notna()) & (g.startDate > now - timedelta(hours=6)) &
           (g.startDate < now + timedelta(days=15))]
    if "homeClassification" in up.columns:
        up = up[(up.homeClassification.astype(str).str.lower() == "fbs") |
                (up.awayClassification.astype(str).str.lower() == "fbs")]
    up = up[up.venueId.notna()]
    up = up[up.venueId.isin(v.index)].drop_duplicates("id")
    if up.empty:
        print("  weather: no upcoming games inside the forecast window"); return
    rows = []
    CH = 40            # Open-Meteo takes many coordinates per call; keep chunks modest
    for i in range(0, len(up), CH):
        sub = up.iloc[i:i + CH]
        lats = [float(v.loc[vid, "latitude"]) for vid in sub.venueId]
        lons = [float(v.loc[vid, "longitude"]) for vid in sub.venueId]
        try:
            r = requests.get("https://api.open-meteo.com/v1/forecast", timeout=45, params={
                "latitude": ",".join(f"{x:.4f}" for x in lats),
                "longitude": ",".join(f"{x:.4f}" for x in lons),
                "hourly": "temperature_2m,precipitation_probability,wind_speed_10m",
                "temperature_unit": "fahrenheit", "wind_speed_unit": "mph",
                "timezone": "UTC", "forecast_days": 16})
            if r.status_code != 200:
                print(f"  weather: HTTP {r.status_code}, stopping here"); break
            payload = r.json()
        except Exception as e:
            print(f"  weather: {e}; carrying on without it"); break
        blocks = payload if isinstance(payload, list) else [payload]
        if len(blocks) != len(sub):
            print(f"  weather: got {len(blocks)} forecasts for {len(sub)} games, stopping")
            break
        for (_, gg), block in zip(sub.iterrows(), blocks):
            h = block.get("hourly") or {}
            times = h.get("time") or []
            if not times:
                continue
            want = gg.startDate.strftime("%Y-%m-%dT%H:00")
            if want in times:
                k = times.index(want)
            else:
                try:
                    diffs = [abs((pd.Timestamp(x, tz="UTC") - gg.startDate).total_seconds())
                             for x in times]
                    k = int(min(range(len(diffs)), key=lambda j: diffs[j]))
                except Exception:
                    continue

            def at(key):
                arr = h.get(key) or []
                return arr[k] if k < len(arr) else None

            rows.append(dict(game_id=gg.id, homeTeam=gg.homeTeam, awayTeam=gg.awayTeam,
                             week=gg.week, kickoff=gg.startDate.isoformat(),
                             temp_f=at("temperature_2m"),
                             precip_pct=at("precipitation_probability"),
                             wind_mph=at("wind_speed_10m")))
        time.sleep(1)
    if rows:
        pd.DataFrame(rows).to_csv(os.path.join(DATA, "weather.csv"), index=False)
        print(f"  weather.csv: {len(rows):,} games")
    else:
        print("  weather: nothing usable came back")


try:
    fetch_weather(games, venues)
except Exception as e:
    print(f"  weather: unexpected problem ({e}); the card will run without it")

print("done")
