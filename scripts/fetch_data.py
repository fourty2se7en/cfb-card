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


def get(path, **params):
    """GET with the key in a header. Retries on transient failures."""
    for attempt in range(4):
        try:
            r = SESSION.get(f"{API}{path}", params=params, timeout=30)
        except requests.RequestException as e:
            print(f"  network error on {path}: {e}"); time.sleep(3 * (attempt + 1)); continue
        if r.status_code == 200:
            return r.json()
        if r.status_code in (401, 403):
            # Never print the key or the full URL on an auth failure.
            sys.exit(f"ERROR: CFBD rejected the key on {path} (HTTP {r.status_code}). "
                     "Check the secret value is the key from your email, with no quotes or spaces.")
        if r.status_code == 429:
            print(f"  rate limited on {path}, waiting"); time.sleep(10 * (attempt + 1)); continue
        print(f"  HTTP {r.status_code} on {path}"); time.sleep(2 * (attempt + 1))
    return None


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
games = save(get("/games", year=SEASON, seasonType="regular"), "games.csv",
             ("id", "week", "homeTeam", "awayTeam", "homePoints", "awayPoints"))

# Betting lines. This is the piece the free GitHub mirror does not carry for the
# current season, and the main reason the key is required. The opening number
# matters as much as the closing one: line movement is research, and the
# backtest measures the model against both.
save(get("/lines", year=SEASON, seasonType="regular"), "lines.csv",
     ("id", "homeTeam", "awayTeam", "lines"))

# Team talent composite — recruiting rolled up to a team rating. No NFL analogue.
for yr in (SEASON, SEASON - 1):
    t = get("/talent", year=yr)
    if t:
        save(t, f"talent_{yr}.csv", ("team", "talent")); break

# Returning production: how much of last year's output is back. Matters far more
# in college than the NFL because rosters turn over so much faster.
save(get("/player/returning", year=SEASON), "returning.csv", ("team",))

# SP+ ratings, CFBD's own opponent-adjusted efficiency measure. Used as an
# independent cross-check, the same role Elo plays in the NFL card.
save(get("/ratings/sp", year=SEASON), "sp_ratings.csv", ("team", "rating"))

# Team identity: colors, conference, classification. The card paints team names
# in their own colors the way the NFL card does, and there is no other source for
# them. Optional in every sense: if this call fails the card simply renders team
# names in the ordinary text color.
save(get("/teams"), "teams.csv", ("school", "color"))

# Venues, for weather, elevation, surface and travel distance.
venues = save(get("/venues"), "venues.csv", ("id", "name", "latitude", "longitude"))

# Prior-season results, so week 1 has priors instead of nothing.
save(get("/games", year=SEASON - 1, seasonType="regular"), "games_prior.csv",
     ("id", "week", "homeTeam", "awayTeam"))


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


def fetch_odds():
    """Per-book NCAAF prices. Best-effort: no key, or any failure, costs nothing."""
    if not ODDS_KEY:
        print("  odds api: no ODDS_API_KEY set, skipping (CFBD lines are unaffected)")
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
            rec = {"commence_time": g.get("commence_time"), "home_team": home,
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


fetch_odds()


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
