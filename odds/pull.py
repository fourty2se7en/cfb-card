"""The Odds API pull for every Season Cards sport (Trina, Nov 9 2026: keep the $30 plan, 20,000 credits a month, use it for all sports).

Runs as the GitHub Action .github/workflows/odds.yml. The key is the ODDS_API_KEY repository secret, sent only as a query
parameter to api.the-odds-api.com (their only auth method) and never printed. Nothing here writes picks; the card runs read
the files this writes (odds/read.py).

Modes
  open        about 07:05 Phoenix. Full game lines (moneyline, spread, total) for every sport with games in the next 30 hours.
              One call per sport, 3 credits. Once per Phoenix day per sport.
  props_open  about 10:05 Phoenix. Player props for every game in the next 30 hours (sports with props). Per game, 1 credit per
              prop market returned, 4 books.
  close       every 30 minutes. Full game lines for games starting in the next 75 minutes (one call per sport, 3 credits, every run,
              the latest read before tip is the close), plus first half or first period lines and closing props once per game.
  status      prints the credits left (costs nothing: the events endpoint is free).

Cost: 1 credit per market per region (us) per call; markets that come back empty cost nothing; the events list is free.
Budget guard (x-requests-remaining): props stop below RESERVE_PROPS, period lines below RESERVE_PERIODS, everything except the
cfb-card refresh pull below RESERVE_ALL.

Files (gzip CSV, one per pull, never rewritten): odds/data/<sport>/<YYYY-MM-DD Phoenix>/<kind>_<HHMM UTC>.csv.gz
Columns: snap, kind, sport, event_id, commence, away, home, book, market, outcome, point, price, player, book_update
State: odds/state.json (what has been opened and closed). Usage log: odds/usage.csv.
"""
import csv, datetime as dt, gzip, io, json, os, sys, time
from pathlib import Path
import requests

API = 'https://api.the-odds-api.com/v4'
if os.environ.get('ODDS_API_BASE', '').startswith('http://127.0.0.1:'): API = os.environ['ODDS_API_BASE']   # local tests only
KEY = os.environ.get('ODDS_API_KEY', '').strip()
ROOT = Path(__file__).resolve().parent
DATA, STATE_F, USAGE_F = ROOT / 'data', ROOT / 'state.json', ROOT / 'usage.csv'
PHX = dt.timezone(dt.timedelta(hours=-7))       # Phoenix, no daylight saving
FULL = 'h2h,spreads,totals'
PROP_BOOKS = 'draftkings,fanduel,betmgm,williamhill_us'
RESERVE_ALL, RESERVE_PERIODS, RESERVE_PROPS = 600, 2500, 4000
CLOSE_WINDOW_MIN = 75   # GitHub can start scheduled runs late; full lines refresh every run inside the window

SPORTS = {
    'nba':   dict(key='basketball_nba',        periods='h2h_h1,spreads_h1,totals_h1',
                  props='player_points,player_rebounds,player_assists,player_threes,player_points_rebounds_assists'),
    'nhl':   dict(key='icehockey_nhl',         periods='h2h_p1,spreads_p1,totals_p1',
                  props='player_points,player_shots_on_goal,player_total_saves'),
    'ncaam': dict(key='basketball_ncaab',      periods='spreads_h1,totals_h1', props=''),
    'ncaaw': dict(key='basketball_wncaab',     periods='h2h_h1,spreads_h1,totals_h1', props=''),
    'nfl':   dict(key='americanfootball_nfl',  periods='h2h_h1,spreads_h1,totals_h1',
                  props='player_pass_yds,player_rush_yds,player_reception_yds,player_receptions,player_pass_tds'),
    'fbs':   dict(key='americanfootball_ncaaf', periods='h2h_h1,spreads_h1,totals_h1',
                  props='player_pass_yds,player_rush_yds,player_reception_yds'),
}
COLS = ['snap', 'kind', 'sport', 'event_id', 'commence', 'away', 'home', 'book', 'market', 'outcome', 'point', 'price', 'player', 'book_update']

NOW = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
LEFT = {'n': None}


def iso(t): return t.strftime('%Y-%m-%dT%H:%M:%SZ')
def parse(s): return dt.datetime.fromisoformat(s.replace('Z', '+00:00'))


def get(path, mode, sport, **params):
    """GET with the key as a query parameter (the API's only auth). Errors never echo the URL, so the key stays out of logs."""
    params['apiKey'] = KEY
    for i in range(3):
        try:
            r = requests.get(f'{API}{path}', params=params, timeout=30)
        except requests.RequestException as e:
            print(f'  {sport} {path.split("/")[-1]}: network error {type(e).__name__}'); time.sleep(3 * (i + 1)); continue
        left, last = r.headers.get('x-requests-remaining'), r.headers.get('x-requests-last')
        if left is not None:
            try: LEFT['n'] = float(left)
            except ValueError: pass
        if last not in (None, '0') or r.status_code != 200:   # free calls (events list) are not logged, so idle runs commit nothing
          with open(USAGE_F, 'a', newline='') as f:
            csv.writer(f).writerow([iso(NOW), mode, sport, path.split('/')[-1] if 'events/' not in path else 'event_odds', r.status_code, last, left])
        if r.status_code == 200: return r.json()
        if r.status_code in (401, 429) or r.status_code >= 500:
            print(f'  {sport}: HTTP {r.status_code}'); time.sleep(5 * (i + 1)) if r.status_code != 401 else None
            if r.status_code == 401: return None
            continue
        print(f'  {sport}: HTTP {r.status_code} {r.text[:200]}'); return None
    return None


def rows(ev, kind, sport):
    out = []
    for b in ev.get('bookmakers', []):
        for m in b.get('markets', []):
            for o in m.get('outcomes', []):
                player = o.get('description', '') if m['key'].startswith('player_') else ''
                out.append([iso(NOW), kind, sport, ev['id'], ev['commence_time'], ev['away_team'], ev['home_team'], b['key'], m['key'],
                            o.get('name'), o.get('point', ''), o.get('price'), player, m.get('last_update', b.get('last_update', ''))])
    return out


def write(sport, kind, data):
    if not data: return
    day = NOW.astimezone(PHX).strftime('%Y-%m-%d')
    d = DATA / sport / day; d.mkdir(parents=True, exist_ok=True)
    f = d / f'{kind}_{NOW.strftime("%H%M")}.csv.gz'
    buf = io.StringIO(); w = csv.writer(buf); w.writerow(COLS); w.writerows(data)
    with gzip.open(f, 'wt', newline='') as z: z.write(buf.getvalue())
    print(f'  {sport} {kind}: {len(data)} rows -> {f.relative_to(ROOT.parent)}')


def state():
    s = json.loads(STATE_F.read_text()) if STATE_F.exists() else {}
    for k in ('opened', 'props_open', 'closed'): s.setdefault(k, {})
    cut = iso(NOW - dt.timedelta(days=3))
    for k in ('props_open', 'closed'): s[k] = {e: t for e, t in s[k].items() if t >= cut}
    return s


def events(sport, frm, to):
    ev = get(f'/sports/{SPORTS[sport]["key"]}/events', 'events', sport, commenceTimeFrom=iso(frm), commenceTimeTo=iso(to), dateFormat='iso')
    return ev or []


def ok(reserve):
    return LEFT['n'] is None or LEFT['n'] >= reserve


def full(sport, kind, ids, mode):
    params = dict(regions='us', markets=FULL, oddsFormat='american', dateFormat='iso')
    if ids: params['eventIds'] = ','.join(ids)
    data = get(f'/sports/{SPORTS[sport]["key"]}/odds', mode, sport, **params) or []
    write(sport, kind, [r for ev in data for r in rows(ev, kind, sport)])
    return data


def per_event(sport, ev_id, markets, kind, mode, books=None):
    params = dict(markets=markets, oddsFormat='american', dateFormat='iso')
    params['bookmakers' if books else 'regions'] = books or 'us'
    return get(f'/sports/{SPORTS[sport]["key"]}/events/{ev_id}/odds', mode, sport, **params)


def run(mode, only=None):
    if not KEY: print('No ODDS_API_KEY: nothing pulled.'); return
    S = state(); day = NOW.astimezone(PHX).strftime('%Y-%m-%d')
    for sport in (only or SPORTS):
        cfg = SPORTS[sport]
        if mode == 'status':
            events(sport, NOW, NOW + dt.timedelta(hours=1)); break
        if not ok(RESERVE_ALL): print(f'Budget guard: {LEFT["n"]:.0f} credits left, stopping.'); break
        if mode == 'open':
            if S['opened'].get(sport) == day: continue
            evs = events(sport, NOW, NOW + dt.timedelta(hours=30))
            if not evs: continue
            if full(sport, 'open', [], mode): S['opened'][sport] = day
        elif mode == 'props_open':
            if not cfg['props']: continue
            evs = [e for e in events(sport, NOW + dt.timedelta(minutes=5), NOW + dt.timedelta(hours=30)) if e['id'] not in S['props_open']]
            out = []
            for e in evs:
                if not ok(RESERVE_PROPS): print('  props skipped: budget guard'); break
                ev = per_event(sport, e['id'], cfg['props'], 'props_open', mode, PROP_BOOKS)
                if ev: out += rows(ev, 'props_open', sport); S['props_open'][e['id']] = iso(NOW)
            write(sport, 'props_open', out)
        elif mode == 'close':
            win = events(sport, NOW + dt.timedelta(minutes=2), NOW + dt.timedelta(minutes=CLOSE_WINDOW_MIN))
            if not win: continue
            full(sport, 'close', [e['id'] for e in win], mode)   # every run inside the window; the reader keeps the latest one before tip
            evs = [e for e in win if e['id'] not in S['closed']]   # period lines and props once per game
            per, pr = [], []
            for e in evs:
                if cfg['periods'] and ok(RESERVE_PERIODS):
                    ev = per_event(sport, e['id'], cfg['periods'], 'close_periods', mode)
                    if ev: per += rows(ev, 'close_periods', sport)
                if cfg['props'] and ok(RESERVE_PROPS):
                    ev = per_event(sport, e['id'], cfg['props'], 'close_props', mode, PROP_BOOKS)
                    if ev: pr += rows(ev, 'close_props', sport)
                S['closed'][e['id']] = iso(NOW)
            write(sport, 'close_periods', per); write(sport, 'close_props', pr)
    STATE_F.write_text(json.dumps(S, indent=1, sort_keys=True))
    print(f'{mode}: credits left {LEFT["n"]}')


if __name__ == '__main__':
    m = sys.argv[1] if len(sys.argv) > 1 else 'close'
    only = [x for x in sys.argv[2].split(',') if x in SPORTS] if len(sys.argv) > 2 and sys.argv[2] else None
    if not USAGE_F.exists(): USAGE_F.write_text('ts,mode,sport,call,status,cost,remaining\n')
    run(m, only)
