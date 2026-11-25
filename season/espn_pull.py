"""ESPN data for every Season Cards sport (Trina A27, Nov 12 2026). Runs in GitHub Actions (season.yml); no login needed.

    python3 season/espn_pull.py <kind> [sports] [YYYY-MM-DD Phoenix]
    kind: finals  yesterday's scoreboard with period scores plus trimmed box scores (grading, game logs, backtests)
          slate   today's scoreboard, injuries, standings, rankings, transactions (pick inputs)
          ahead   scoreboards for the next 7 Phoenix days (Upcoming games on Season Cards; Trina Nov 19, B161)
          news    today's game previews, game news, injuries and league headlines (Trina Nov 24, A92: why a line moved)
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


def ahead(sport, day, days=7):
    path, grp = SP[sport]; n = 0; d0 = dt.date.fromisoformat(day)
    for i in range(1, days + 1):
        d = (d0 + dt.timedelta(days=i)).isoformat()
        n += save(sport, d, 'scoreboard_ahead', j(f"https://site.api.espn.com/apis/site/v2/sports/{path}/scoreboard?dates={d.replace('-','')}&limit=500" + (f'&groups={grp}' if grp else '')))
    return n


def trim_news(s):
    """Per game: the preview article, linked news, both teams' injury lists and the line history ESPN shows."""
    art = s.get('article') or {}
    news = [dict(h=a.get('headline'), d=a.get('description'), t=a.get('published'), u=((a.get('links') or {}).get('web') or {}).get('href'))
            for a in ((s.get('news') or {}).get('articles') or [])[:8]]
    inj = []
    for t in s.get('injuries') or []:
        ab = (t.get('team') or {}).get('abbreviation')
        for x in t.get('injuries') or []:
            inj.append(dict(team=ab, player=((x.get('athlete') or {}).get('displayName')), status=x.get('status'),
                            detail=((x.get('details') or {}).get('type') or '') + (' ' + (x.get('details') or {}).get('detail', '') if (x.get('details') or {}).get('detail') else ''),
                            date=x.get('date')))
    return dict(preview=dict(h=art.get('headline'), d=art.get('description'), type=art.get('type'), t=art.get('published') or art.get('lastModified'), story=(art.get('story') or '')[:4000]) if art else None,
                news=news, injuries=inj, notes=[n.get('headline') for n in (s.get('header') or {}).get('competitions', [{}])[0].get('notes', []) if n.get('headline')])


def depth(sport, day):
    """Depth charts (Nov 25, validate lineups): every team playing in the next 7 Phoenix days (football; works for any sport ESPN serves).
    Uses the core API depthcharts (athletes as $ref) plus the site roster to resolve names and positions."""
    path, grp = SP[sport]; teams = {}
    import datetime as dt
    d0 = dt.date.fromisoformat(day)
    for k in range(7):
        dd = (d0 + dt.timedelta(days=k)).strftime('%Y%m%d')
        sb = j(f"https://site.api.espn.com/apis/site/v2/sports/{path}/scoreboard?dates={dd}&limit=500" + (f'&groups={grp}' if grp else ''))
        for e in (sb or {}).get('events', []):
            for c in ((e.get('competitions') or [{}])[0].get('competitors') or []):
                t = c.get('team') or {}
                if t.get('id'): teams[t['id']] = t.get('abbreviation')
    lg, ln = path.split('/')
    out = {}
    for tid, ab in teams.items():
        dc = j(f'https://site.api.espn.com/apis/site/v2/sports/{path}/teams/{tid}/depthcharts')
        ro = j(f'https://site.api.espn.com/apis/site/v2/sports/{path}/teams/{tid}/roster')
        names = {}
        for grp_ in (ro or {}).get('athletes', []) or []:
            for a in (grp_.get('items') if isinstance(grp_, dict) and 'items' in grp_ else [grp_]):
                if isinstance(a, dict) and a.get('id'): names[str(a['id'])] = dict(n=a.get('displayName'), pos=(a.get('position') or {}).get('abbreviation'),
                                                                               status=((a.get('injuries') or [{}])[0] or {}).get('status'))
        if not ((dc or {}).get('depthchart') or (dc or {}).get('items')):   # college: core API depth chart, athletes as $ref ids
            yr = int(day[:4]) if int(day[5:7]) >= 7 else int(day[:4]) - 1
            core = j(f'https://sports.core.api.espn.com/v2/sports/{lg}/leagues/{ln}/seasons/{yr}/teams/{tid}/depthcharts?limit=50')
            items = []
            for it in (core or {}).get('items', []):
                pos = {}
                for k2, v2 in (it.get('positions') or {}).items():
                    pos[k2] = {'athletes': [dict(athlete=dict(id=str((x.get('athlete') or {}).get('$ref', '')).rstrip('/').split('/')[-1].split('?')[0]), rank=x.get('rank'))
                                            for x in (v2.get('athletes') or [])]}
                items.append(dict(name=it.get('name'), positions=pos))
            dc = {'items': items}
        charts = []
        for ch in (dc or {}).get('depthchart', []) or (dc or {}).get('items', []) or []:
            pos = {}
            for k, v in (ch.get('positions') or {}).items():
                pos[k] = [dict(id=str((x.get('athlete') or {}).get('id') or x.get('id') or ''), n=(x.get('athlete') or {}).get('displayName') or x.get('displayName') or (names.get(str((x.get('athlete') or {}).get('id') or '')) or {}).get('n'), rank=x.get('rank'))
                          for x in (v.get('athletes') or [])]
            charts.append(dict(name=ch.get('name'), positions=pos))
        out[ab or tid] = dict(id=tid, charts=charts, roster=names)
    return save(sport, day, 'depth', out) and len(out)


def news(sport, day):
    """Today's slate: one summary per game (preview, game news, injuries) plus the league's latest headlines."""
    path, grp = SP[sport]; out = {}
    sb = j(f"https://site.api.espn.com/apis/site/v2/sports/{path}/scoreboard?dates={day.replace('-','')}&limit=500" + (f'&groups={grp}' if grp else ''))
    for e in (sb or {}).get('events', []):
        s = j(f'https://site.api.espn.com/apis/site/v2/sports/{path}/summary?event={e["id"]}')
        if s:
            c = (e.get('competitions') or [{}])[0]
            out[e['id']] = dict(teams=[(x.get('team') or {}).get('abbreviation') for x in c.get('competitors', [])], **trim_news(s))
    lg = j(f'https://site.api.espn.com/apis/site/v2/sports/{path}/news?limit=50')
    out['_league'] = [dict(h=a.get('headline'), d=a.get('description'), t=a.get('published'),
                           teams=[(c.get('team') or {}).get('abbreviation') or c.get('description') for c in a.get('categories', []) if c.get('type') == 'team'])
                      for a in (lg or {}).get('articles', [])]
    return save(sport, day, 'news', out) and len(out)


if __name__ == '__main__':
    kind = sys.argv[1]; sports = [s for s in (sys.argv[2].split(',') if len(sys.argv) > 2 and sys.argv[2] else SP) if s in SP]
    day = sys.argv[3] if len(sys.argv) > 3 else dt.datetime.now(PHX).strftime('%Y-%m-%d')
    for s in sports:
        try: print(s, kind, {'finals': finals, 'ahead': ahead, 'news': news, 'depth': depth}.get(kind, slate)(s, day))
        except Exception as e: print(s, kind, 'error', type(e).__name__, str(e)[:120])
