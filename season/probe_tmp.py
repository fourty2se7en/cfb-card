import requests, json, sys
S = requests.Session()
H = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
     'Referer': 'https://www.nba.com/', 'Origin': 'https://www.nba.com', 'x-nba-stats-origin': 'stats', 'x-nba-stats-token': 'true',
     'Accept': 'application/json, text/plain, */*', 'Accept-Language': 'en-US,en;q=0.9'}
def show(u, h=None, n=1500):
    try:
        r = S.get(u, headers=h or {'User-Agent': 'season-cards-data/1.0'}, timeout=40)
        print('##', u, r.status_code, len(r.content)); t = r.text
        print(t[:n].replace('\n', ' ')); return r
    except Exception as e: print('##', u, 'ERR', type(e).__name__, str(e)[:200])
show('https://stats.nba.com/stats/playergamelogs?LeagueID=00&Season=2026-27&SeasonType=Regular%20Season', H, 600)
r = show('https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/3934672/gamelog?season=2026', None, 200)
if r is not None and r.ok:
    j = r.json(); print('KEYS', list(j.keys())); print('labels', j.get('labels')); print('names', j.get('names'))
    ev = j.get('events', {}); k = next(iter(ev)) if ev else None; print('EV', json.dumps(ev.get(k))[:700] if k else None)
    for st in j.get('seasonTypes', [])[:3]:
        print('ST', st.get('displayName'), [ (c.get('type'), c.get('displayName'), len(c.get('events', []))) for c in st.get('categories', [])])
        for c in st.get('categories', [])[:1]: print('E0', json.dumps(c.get('events', [])[:1])[:300])
r = show('https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/13/roster', None, 300)
if r is not None and r.ok: a = r.json().get('athletes', []); print('ROSTER', len(a), json.dumps(a[0])[:400] if a else '')
r = show('https://site.web.api.espn.com/apis/common/v3/sports/football/college-football/athletes/4432577/gamelog', None, 200)
r = show('https://api.nhle.com/stats/rest/en/team/summary?cayenneExp=seasonId=20262027%20and%20gameTypeId=2', None, 900)
r = show('https://sports.core.api.espn.com/v2/sports/football/leagues/college-football/seasons/2026/types/2/teams/2/statistics', None, 200)
if r is not None and r.ok:
    j = r.json(); cats = j.get('splits', {}).get('categories', [])
    for c in cats[:12]: print('CAT', c.get('name'), [(s.get('name'), s.get('perGameValue'), s.get('rank')) for s in c.get('stats', [])[:6]])
# box score athlete position?
import gzip
b = json.load(gzip.open('season/data/espn/nba/2026-11-13/boxscores.json.gz'))
g = next(iter(b.values())); p = g['players'][0]; print('NBA BOX', json.dumps(p)[:900])
b = json.load(gzip.open('season/data/espn/fbs/2026-11-13/boxscores.json.gz'))
g = next(iter(b.values())); print('FBS TEAMS', json.dumps(g['teams'])[:900]); print('FBS PL', json.dumps(g['players'][0])[:900])
b = json.load(gzip.open('season/data/espn/ncaam/2026-11-13/boxscores.json.gz'))
g = next(iter(b.values())); print('NCAAM TEAMS', json.dumps(g['teams'])[:1200])
