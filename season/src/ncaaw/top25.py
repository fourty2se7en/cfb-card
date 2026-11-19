"""AP Top 25 scope for the NCAAW card (Trina, Nov 9 2026).
Card picks, would-be picks, game docs, the re-check (rule status records) and the season backtest use only games where at least one
team is in the AP Top 25 at game time. Standings keep every conference and every team.
Rank at game time: ESPN curatedRank on that day's scoreboard (season rows hRank/aRank, fields 10 and 11; slate fields ar/hr).
When a slate row has no rank field, data/ap_poll.json (the current AP poll) is the fallback.
The poll changes weekly: every run pulls the current AP poll; poll_warning() flags a poll older than 8 days during the season."""
import json, pathlib, datetime

DATA = pathlib.Path(__file__).resolve().parent.parent/'data'
ON = {'W'}   # leagues that use the scope (NCAAM is unchanged)


def ranked(r):
    try: return r not in (None, '') and 1 <= int(r) <= 25
    except (TypeError, ValueError): return False


def poll(lg='W'):
    p = DATA/'ap_poll.json'
    if not p.exists(): return {}, None
    ap = json.loads(p.read_text())
    return {x['team']: x['rank'] for x in ap.get(lg, []) if ranked(x.get('rank'))}, ap


def slate_in_scope(g, lg='W', teams=None):
    """Today's game: ESPN slate ranks first, then the current AP poll."""
    if lg not in ON: return True
    if ranked(g.get('ar')) or ranked(g.get('hr')): return True
    teams = teams if teams is not None else poll(lg)[0]
    return g.get('away') in teams or g.get('home') in teams


def row_in_scope(hr, ar, lg='W'):
    """A played game (season row): ranks at game time."""
    return lg not in ON or ranked(hr) or ranked(ar)


def scope_keys(games_rows, lg='W'):
    """(date, home, away) of in-scope lined games from season/games_<lg>.txt rows, for the box-score (efficiency) rules."""
    return {(r[2], r[3], r[4]) for r in games_rows if row_in_scope(r[10], r[11], lg)}


def poll_warning(today, lg='W'):
    _, ap = poll(lg)
    if not ap: return 'AP poll file missing: pull the current AP Top 25 before building the card.'
    d = ap.get(f'{lg}_date')
    if not d: return 'AP poll file has no poll date: re-pull the AP Top 25 (ESPN rankings) and save W_date and W_week.'
    age = (datetime.date.fromisoformat(today) - datetime.date.fromisoformat(d)).days
    if age > 8: return f'AP poll is {age} days old ({ap.get(lg + "_week", "")}, {d}): pull the new weekly poll before building the card.'
    return None
