"""
fetch_data.py — pull current college football data from CollegeFootballData.

The API key is read from the CFBD_API_KEY environment variable, which GitHub
Actions supplies from the encrypted repository secret. It is sent in an
Authorization HEADER, never in the URL. URLs leak into error messages, stack
traces and run logs; headers do not.

Writes plain CSVs into data/ so the rest of the pipeline needs no key at all.
"""
import os, sys, time, json
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
save(get("/games", year=SEASON, seasonType="regular"), "games.csv",
     ("id", "week", "homeTeam", "awayTeam", "homePoints", "awayPoints"))

# Betting lines. This is the piece the free GitHub mirror does not carry for the
# current season, and the main reason the key is required.
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

# Prior-season results, so week 1 has priors instead of nothing.
save(get("/games", year=SEASON - 1, seasonType="regular"), "games_prior.csv",
     ("id", "week", "homeTeam", "awayTeam"))

print("done")
