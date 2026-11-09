# Odds (The Odds API, all Season Cards sports)

Trina, Nov 9 2026: the $30 plan (20,000 credits a month) is used for every sport.

- Workflow: `.github/workflows/odds.yml`, key from the `ODDS_API_KEY` secret (same as cfb-card.yml).
- Pull: `odds/pull.py` (open 07:05 Phoenix, opening props 10:05, closing lines every 30 minutes for games starting within 50 minutes).
- Files: `odds/data/<sport>/<Phoenix date>/<kind>_<HHMM UTC>.csv.gz`, never rewritten. Kinds: open, props_open, close, close_periods, close_props.
- Read: `python3 odds/read.py <sport> <date> [out.json]` gives the median open and close lines, first half or first period closes and props per game.
- Sports: nba, nhl, ncaam, ncaaw, nfl, fbs. Budget guard and costs are in pull.py. Credits used: `odds/usage.csv`.
