"""ESPN data for every Season Cards sport (Trina A27, Nov 12 2026). Runs in GitHub Actions (season.yml); no login needed.

    python3 season/espn_pull.py <kind> [sports] [YYYY-MM-DD Phoenix]
    kind: finals  yesterday's scoreboard with period scores plus trimmed box scores (grading, game logs, backtests)
          slate   today's scoreboard, injuries, standings, rankings, transactions (pick inputs)
Writes season/data/espn/<sport>/<date>/<name>.json.gz. A missing feed is skipped, never fatal."""
import datetime as dt, gzip, json, sys, time
from pathlib import Path
import requests

PHX = dt.timezone(dt.timedelta(hours=-7))
SP = {'nba': ('basketball/nba', ''), 'nhl': ('hockey/nhl', ''), 'nfl': ('football/nfl', ''), 'fbs': ('football/college-football', '80'),
      'ncaam': ('basketball/mens-college-basketball', '50'), 'ncaaw': ('basketball/womens-college-basketball', '50')}
S = requests.Session(); S.headers['User-Agent'] = 'season-cards-data/1.0'
BASE = Path(__file__).resolve().parent / 'data' / 'espn'


def j(url):
    for i in range(3):
        try:
            r = S.get(url, timeout=30)
            if r.ok: return r.json()
            if r.status_code == 404: return None
        except requests.RequestException: pass
        time.sleep(1 + i)
    return None


def save(sport, day, name, obj):
    if obj is None: return 0
    d = BASE / sport / day; d.mkdir(parents=True, exist_ok=True)
    with gzip.open(d / f'{name}.json.gz', 'wt') as z: json.dump(obj, z, separators=(',', ':'))
    return 1


def trim_summary(s):
    """Keep what grading, game logs and props need: teams, scores, period scores, team stats, player stats."""
    hdr = (s.get('header') or {}).get('competitions', [{}])[0]
    return dict(id=(s.get('header') or {}).get('id'), status=((hdr.get('status') or {}).get('type') or {}).get('name'),
                competitors=[dict(home_away=c.get('homeAway'), abbr=(c.get('team') or {}).get('abbreviation'), location=(c.get('team') or {}).get('location'),
                                  score=c.get('score'), linescores=[x.get('displayValue') for x in c.get('linescores', [])]) for c in hdr.get('competitors', [])],
                teams=(s.get('boxscore') or {}).get('teams'), players=(s.get('boxscore') or {}).get('players'))


def finals(sport, day):
    path, grp = SP[sport]; yday = (dt.date.fromisoformat(day) - dt.timedelta(days=1)).isoformat()
    sb = j(f"https://site.api.espn.com/apis/site/v2/sports/{path}/scoreboard?dates={yday.replace('-','')}&limit=500" + (f'&groups={grp}' if grp else ''))
    if not sb: return 0
    save(sport, yday, 'scoreboard_final', sb); n = 0; box = {}
    for e in sb.get('events', []):
        if ((e.get('status') or {}).get('type') or {}).get('state') != 'post': continue
        s = j(f'https://site.api.espn.com/apis/site/v2/sports/{path}/summary?event={e["id"]}')
        if s: box[e['id']] = trim_summary(s); n += 1
    save(sport, yday, 'boxscores', box)
    return n


def slate(sport, day):
    path, grp = SP[sport]; n = 0
    n += save(sport, day, 'scoreboard', j(f"https://site.api.espn.com/apis/site/v2/sports/{path}/scoreboard?dates={day.replace('-','')}&limit=500" + (f'&groups={grp}' if grp else '')))
    n += save(sport, day, 'injuries', j(f'https://site.api.espn.com/apis/site/v2/sports/{path}/injuries'))
    n += save(sport, day, 'standings', j(f'https://site.web.api.espn.com/apis/v2/sports/{path}/standings'))
    if sport in ('fbs', 'ncaam', 'ncaaw'): n += save(sport, day, 'rankings', j(f'https://site.api.espn.com/apis/site/v2/sports/{path}/rankings'))
    if sport in ('nba', 'nhl', 'nfl'): n += save(sport, day, 'transactions', j(f'https://site.api.espn.com/apis/site/v2/sports/{path}/transactions'))
    return n


if __name__ == '__main__':
    kind = sys.argv[1]; sports = [s for s in (sys.argv[2].split(',') if len(sys.argv) > 2 and sys.argv[2] else SP) if s in SP]
    day = sys.argv[3] if len(sys.argv) > 3 else dt.datetime.now(PHX).strftime('%Y-%m-%d')
    for s in sports:
        try: print(s, kind, (finals if kind == 'finals' else slate)(s, day))
        except Exception as e: print(s, kind, 'error', type(e).__name__, str(e)[:120])
